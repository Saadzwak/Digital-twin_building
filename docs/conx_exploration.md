# ConX — Exploration approfondie (Phase 1)

Dossier exploré : `C:\Users\redaz\Desktop\CD2E` (projet ConX, code lu intégralement,
aucune modification). ConX = plateforme IA de priorisation et de conception de
rénovations énergétiques hors-site décarbonées, centrée Hauts-de-France, sur
données 100 % publiques (Licence Ouverte Etalab 2.0).

Ce document est un état des lieux pour décider ce qu'on intègre à notre plateforme
Pleiades. **Il ne code rien.** J'attends votre validation avant la Phase 5.

---

## 1. DONNÉES

### 1.1 Jeux de données, champs, couverture

| Source | Fournisseur | Contenu utile | Couverture | Format brut présent |
|---|---|---|---|---|
| **BDNB** millésime 2025-07.a | CSTB | >400 attributs/bâtiment : géométrie, surface, hauteur, année, nb logements, matériau, DPE, RNB, parcelle, **typologie propriétaire** (jamais l'identité) | 5 dpts HDF : 59, 62, 80, 60, 02 | ✅ pgdumps zippés `data/raw/bdnb/{dpt}/…zip` |
| **DPE** ADEME | ADEME | classe énergie/GES A-G, kWh ep/m²/an, kgCO₂/m²/an, équipements chauffage/ECS/ventilation, U-values, déperditions par poste | idem, jointure `rnb_id`→adresse→parcelle | via BDNB (table `dpe_representatif_logement`) |
| **BD TOPO** | IGN | emprise + hauteur bâtiment, largeur voirie (accès chantier) | 5 dpts | ✅ `.7z` `data/raw/bdtopo/` |
| **BD Ortho** | IGN | orthophotos 20 cm/px, streaming WMTS `data.geopf.fr` | France, streaming direct | pas de stockage (WMTS) |
| **BAN** | DGFiP | géocodage adresse ↔ point, autocomplétion | France | API publique |
| **LiDAR HD** | IGN | nuage de points classifié 10 pts/m², dalles 1 km² | 59+62 open depuis 2024 ; 02/60/80 progressif | ❌ non téléchargé (stub) |
| **INIES FDES** | INIES | kgCO₂eq/UF matériaux, carbone biogénique stocké | 30 matériaux clés | ✅ `data/fdes_static.json` |
| **Base Carbone** | ADEME | facteurs d'émission kgCO₂/kWh par énergie | — | ✅ constantes dans le code |

### 1.2 Directement réutilisable tel quel

- **`data/fdes_static.json`** (30 matériaux) : id, nom, `kgCO2eq_per_uf`, `biogenic_co2_stored_kg`, λ, densité. Biosourcés à bilan négatif (bois CLT −28,5 ; MOB −42,0). **Portable immédiatement.**
- **`data/marketplace_companies.json`** (25 entreprises HDF réelles de la rénovation hors-site biosourcée : Goudalle Charpente, etc.), avec spécialités, ville, département, site. Sources Fibois HDF / CD2E.
- **`config/scoring_thresholds.yaml`** et **`config/zone_climatique_dpt.yaml`** : tous les seuils, facteurs, grilles de coût €/m², tables sociales et passoire.
- **Enregistrements bâtiment réels documentés** (pas de base à faire tourner) : le rapport `docs/BUILDING_DATA_INVENTORY.md` contient le dossier **complet et réel** d'un bâtiment de Wazemmes (98 Rue des Sarrazins, Lille, bailleur social R+4 1978, DPE F, 48 logts, U_mur=1,0, déperditions par poste, chauffage gaz collectif, **pas de VMC**, **pas d'ITE**, raccordable réseau de chaleur, QPV) + 5 voisins avec classe DPE et distance. `docs/VIEUX_LILLE_ANALYSE.md` documente 3 autres candidats réels (copros anciennes, scores 77–91, CO₂ 300–714 t, coûts 88–140 k€).

### 1.3 Données 3D IGN — format, qualité, exploitabilité

**Verdict : NON exploitable en l'état pour notre démo.**
- Le pipeline LiDAR HD est un **stub** (`scripts/lidar_to_gltf.py`, `docs/LIDAR_PIPELINE.md`). Aucune dalle LAZ n'a été téléchargée (`data/storage/lidar/` vide), aucun mesh glTF n'a été généré. Le crop par bâtiment (PostGIS) est marqué TODO.
- La conversion exige PDAL (via Docker `pdal/pdal`) + triangulation Poisson (~30–90 s/dalle) puis `trimesh`. Lourd, hors-ligne, non branché à un endpoint.
- **Ce qui existe et marche à la place** : l'extrusion 3D depuis BD TOPO (emprise + `hauteur_m`) et la géométrie BDNB (MultiPolygon) extrudée dans deck.gl. C'est la « couche universelle 3D » qui couvre tout HDF sans LiDAR. **C'est la voie réaliste.**

---

## 2. APPROCHES

### 2.1 Visualisation du parc / bâtiment / géographie

Stack front : **React + TS + Vite + Tailwind + MapLibre GL + deck.gl v9** (pas de Three.js, pas de Mapbox). Deux modes :

- **Mode Stratégie (macro/parc)** : carte MapLibre, fond OSM qui bascule en ortho IGN au zoom, overlay deck.gl `ScatterplotLayer` des centroïdes bâtiments — **couleur = classe DPE (rampe A→G vert→rouge)**, **rayon = score ConX** (« plus gros = plus prioritaire »). Filtres à gauche (preset « Passoires F-G », bailleur social…), recherche adresse BAN, statut « N bâtiments » bottom-left, tuiles vectorielles MVT via Martin. Choropleth densité passoires par EPCI/commune (matview `commune_passoires_heatmap_mv`).
- **Mode Projet (micro/bâtiment)** : carte oblique (pitch 50°) avec le bâtiment cible **extrudé et coloré par DPE** + voisins extrudés gris (MVTLayer). Sidebar riche : carte compacte → 6 accordéons experts (diagnostic technique, conso réelle 7 ans, distribution DPE RPLS, coût+classement, aides éligibles, risques+urbanisme). Agent IA de plan rénovation en streaming SSE.

### 2.2 Chiffrage des scénarios de rénovation

- **Score ConX déterministe** (`docs/SCORING.md`, gelé D-006) : 5 composantes normalisées [0,1] pondérées (CO₂ évité 0.35, faisabilité 0.25, coût 0.20, social 0.10, passoire 0.10) → 0–100. Seuils absolus (0–500 tCO₂ ; 500–5000 €/tCO₂). Poids ajustables par sliders, renormalisés. **L'IA n'invente jamais un chiffre — elle narre.**
- **Coût** : `surface × coût_m2(typologie, période)` (grille ADEME dans le YAML) × modulateur géométrie/patrimoine.
- **Plan rénovation** : généré par un agent LLM hébergé (system prompt `plan.md`), **prose + tableaux markdown**, itératif (chips v1/v2 « plutôt chanvre »), sources FDES citées, liens marketplace. Le carbone reste calculé en Python déterministe.

### 2.3 Coût, CO₂, réglementation

- **Carbone (`backend/app/carbon/`, pur Python, 32 tests)** : 3 composantes — **exploitation** (gain CO₂ = Δconso × surface × facteur × horizon), **incorporé** (Σ matériaux FDES, carbone biogénique séparé), **évité hors-site** (fraction CSTB 25 %, fourchette 20–40 %). Verdict « vertueux/émissif ». Convention de signes explicite. **Chiffre = source citable.**
- **Aides (`_aides_eligibles` dans buildings.py, pur Python)** : matrice de règles → Eco-PLS (bailleur social, nb_logts × 16 000 €), ANRU (QPV), CEE passoire, MaPrimeRénov' Copro, raccordement RCU prioritaire, Fonds Vert. Portable telle quelle.
- **Réglementation** : classe DPE + périodes thermiques (RT1974→RE2020), passoire loi Climat, coefficient EP électricité **1.9** (réforme 2026, aligné). Réseau de chaleur : périmètre prioritaire de raccordement.

### 2.4 Ce qui marche visuellement et mérite d'être repris

- **Rampe DPE A→G** (lettre en tuile colorée) — encodage catégoriel instantané, réutilisable pour toute échelle ordinale.
- **Choropleth par attribut + taille par score** sur MapLibre+deck.gl — carte de priorité légère, efficace.
- **`ScoreCircle`** (jauge donut conic-gradient CSS) + **`BigStat`** (tuiles KPI animées `useCountUp`) — sans dépendance, soignés.
- **`ScoreRadar`** (recharts, pentagone 5 axes), **barres de déperdition normalisées**, **barre empilée unique** (distribution DPE).
- **Chips réglementaires** (QPV, RCU, Zone AC1, MH, non-PMR) avec tooltips d'acronymes.
- **Architecture progressive** : carte compacte → accordéons experts (divulgation progressive).
- **SSE streaming avec reprise/backoff + fallback cache + chips de version** pour le plan IA.

---

## 3. CODE

### 3.1 Modules réutilisables directement (pur Python, portables)

| Module | Dépendances | Ce qu'il fait |
|---|---|---|
| `backend/app/carbon/*` + `data/fdes_static.json` | aucune | **Le joyau.** Calcul CO₂ déterministe 3 composantes + base matériaux. |
| `_aides_eligibles(...)` (buildings.py) | aucune | Moteur de règles aides françaises. Extractible tel quel. |
| `backend/app/scoring/compute.py` | PyYAML | `compute_components(building, dpe, thresholds)` — les 5 composantes. |
| `backend/app/ml/{features,predict,train}.py` | pandas/sklearn | Estimateur DPE RandomForest (classe + kWh) quand pas de DPE réel. |
| `skills/ifc-check/ifc_validator.py` | ifcopenshell | Validateur IFC RE2020/PMR mono-fichier. |
| `backend/app/plan_export.py` + `pdf_utils.py` | jinja2/weasyprint | Markdown→PDF durci. |

### 3.2 Patterns de visualisation à reprendre

- Setup **MapLibre + deck.gl `MapboxOverlay`** (bascule OSM↔ortho par zoom, bus d'événements `conx:flyto`).
- **ScatterplotLayer couleur=catégorie / rayon=score**.
- Jauge conic-gradient + compteurs `useCountUp` + tuiles KPI.
- Barres empilées / normalisées en CSS pur (déperditions, distribution, classement).
- Skeleton mimétique + chips-tooltip d'acronymes.

### 3.3 Ce qui est spécifique à ConX et ne transpose pas

- Tout ce qui est **couplé à leur PostGIS/BDNB** (routers, ingestion, scripts SQL, tuiles Martin) — nécessite leur stack Docker + 15–30 Go de données.
- La **sémantique franco-réglementaire** (DPE/GES, RPLS, QPV, RCU, Zone AC1/ABF, MaPrimeRénov, RE2020/PMR) — contenu métier, pas un composant.
- Les **agents LLM hébergés (managed agents)** (plan/sélection/conformité) + Supabase RLS.
- Le pipeline **LiDAR→glTF** (stub, non fonctionnel).
- Dépendances **installées mais inutilisées** (Radix, `@deck.gl/mesh-layers`) — ne pas déduire les capacités du seul `package.json`.

---

## 4. RECOMMANDATION

Notre plateforme Pleiades identifie la **physique thermique d'UN bâtiment** (jumeau, dérive, scénarios). ConX apporte l'**échelle du parc, la comparaison, le chiffrage rénovation € / CO₂ / réglementation**. Les deux sont complémentaires : Pleiades = « ce bâtiment se comporte comment et pourquoi » ; ConX = « ce bâtiment vaut-il d'être rénové, à quel coût, avec quelles aides, par rapport à ses voisins ».

### À intégrer — par ordre d'impact visuel × faisabilité

1. **Moteur carbone déterministe + FDES (`carbon/` + `fdes_static.json`)** — impact fort, effort faible. Pur Python, se branche direct. Donne CO₂ évité 30 ans, carbone incorporé, biogénique stocké, verdict — **avec sources citables**. C'est ce qui transforme nos scénarios (aujourd'hui en % d'énergie) en **tCO₂ et €**.
2. **Chiffrage € + aides éligibles (`scoring` coût + `_aides_eligibles`)** — impact fort, effort faible. Coût €/m² par typologie, €/tCO₂, matrice d'aides (Eco-PLS, MaPrimeRénov, CEE, RCU, Fonds Vert). Alimente le **tableau de décision classé par ROI** demandé.
3. **Un bâtiment réel HDF comme sujet parc/rénovation** — impact fort, effort faible. Utiliser **Wazemmes** (98 Rue des Sarrazins) : dossier BDNB complet et réel déjà documenté, distinct de Pleiades. Permet toute la partie ConX **sans faire tourner leur Postgres**.
4. **Carte du parc (MapLibre + deck.gl, couleur DPE / taille score)** — impact visuel très fort, effort moyen. Sur Wazemmes + voisins réels (5 voisins documentés avec DPE + distance). Fond ortho IGN WMTS (streaming, gratuit).
5. **KPI owner regroupés** (gain énergie / € par an / CO₂ par an / conformité) via `BigStat` + jauge — impact fort, effort faible.
6. **Cadre réglementaire** (passoire loi Climat, coefficient 1.9, réseau de chaleur, période thermique) en chips — impact moyen, effort faible.
7. **Comparaison aux bâtiments similaires** (voisins DPE + distance, distribution) — impact moyen, effort faible.

### À écarter — et pourquoi

- **LiDAR HD → glTF** : stub non fonctionnel, aucune donnée présente, pipeline lourd hors-ligne (PDAL/Docker). On garde **notre bâtiment 3D SVG axonométrique** existant, ou une extrusion simple type BD TOPO. Impossible à livrer proprement dans le temps.
- **Stack complète ConX (Postgres/PostGIS + Martin + Supabase + Docker + 15–30 Go)** : trop lourd à faire tourner ; on prend les **modules purs et les données réelles documentées** à la place.
- **Agents LLM hébergés (managed agents) pour le plan** : notre chat est déjà contraint et déterministe ; on n'ajoute pas une dépendance agentique externe.
- **Marketplace / commandes groupées** : hors périmètre de la demande (gain/€/CO₂/conformité + décision ROI).
- **1,5 M bâtiments à l'écran** : on n'a pas la base ; on montre **un parc réaliste ciblé** (Wazemmes + voisins), suffisant pour la démonstration et honnête.

### Distinction Pleiades ↔ ConX (obligatoire, visible)

Deux bâtiments distincts, clairement étiquetés :
- **Pleiades (Espagne, Murcie)** = identification thermique par les mesures horaires (ce qu'on a déjà).
- **Wazemmes (HDF, France)** = parc, comparaison, rénovation chiffrée (partie ConX).

L'interface doit dire lequel est lequel à chaque écran.

### Règle intangible

Aucun chiffre fabriqué. Tout nombre affiché vient d'un calcul exécuté (moteur carbone/coût déterministe) ou d'une donnée réelle (BDNB documentée, FDES, facteurs ADEME). Toute hypothèse nécessaire est nommée en une ligne.

---

**J'attends votre validation de ce document avant de coder l'intégration ConX (Phase 5).**
En attendant, je traite les Phases 2 (deux bugs) et 3 (passage en anglais) sur le dashboard actuel.
