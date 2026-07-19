# Auto-critique hostile — refonte salle de contrôle

Date : 2026-07-19. Nouvelle interface : `webapp/` (FastAPI + SPA sombre, bâtiment
3D SVG, topologie RC animée). L'ancienne UI Streamlit reste en place mais n'est
plus le produit.

## Ce qui a été exécuté et vérifié (DOM, console, tests)

- Parcours complet en navigateur : accueil → démo → exécution en direct →
  onboarding → dashboard → survol scénario → chat réussi → chat refusé.
- Console **zéro erreur/zéro log** sur tout le parcours (vérifié via
  read_console_messages).
- Toutes les séries SVG (bâtiment, dérive, scénarios, nuage, topologie) sans
  NaN/Inf (scan DOM : 0 valeur non finie). Vega supprimé.
- 78 tests verts, dont 6 nouveaux (`test_webapp.py` : sanitize, graphes de
  topologie, cohérence sélection↔jumeau, géométrie honnête).

## Corrections demandées

- **A — cohérence sélection/jumeau.** Mesure faite : la règle MSE-train est
  déjà stable (LADDER_1R1C parmi les admissibles à N=3,6,10,16). Fait
  décisif établi sur données scellées : les départs 4R3C au meilleur RMSE
  validation sont **dégénérés** (val 1,98 mais train 41,7, UA ~10⁶–10⁸ W/K),
  et le train-best est le bassin générique ; seule la calibration publiée
  donne un UA physique (63 W/K). L'identification automatique **ne peut donc
  pas** sélectionner un jumeau physique — l'écart est réel, pas un bug.
  Résolution (fallback prévu par la consigne) : l'en-tête affiché = la
  structure du jumeau (4R3C) ; la sélection automatique du banc (1R1C) est
  **surfacée et déclarée**, pas masquée ; `consistent_with_selection=true`.
- **B — NaN/Inf.** Choke point unique `sanitize.clean` sur chaque réponse API ;
  charts SVG maison avec garde `isFinite`. Console propre confirmée.

## Critique adversariale

1. **Affirmation fragile ?** « Le banc sélectionne 4R3C » serait faux : le banc
   AUTOMATIQUE sélectionne 1R1C. **Corrigé :** l'interface dit que le banc
   explore et retombe sur la plus simple, et que le jumeau est la calibration
   de référence — explicitement, en surface (méthodo dépliée + événement de
   sélection).
2. **Chiffre sans incertitude ?** KPI et cartes portent leurs fourchettes ;
   déperdition marquée « non robuste entre calages ».
3. **Hypothèse enterrée ?** Le mode « replay d'un calcul réel » est badgé à
   l'écran et déclaré ; la géométrie porte sa mention volume + non validée.
4. **Spécifique au jeu de données ?** Le jumeau-référence 4R3C n'existe que
   pour PLEIAData ; un upload reçoit la sélection du banc (jumeau = banc,
   cohérent par construction) avec ses limites.
5. **« Ça marche » non exécuté ?** Le screenshot navigateur est indisponible
   dans cet environnement (timeout systématique, même sur page vierge —
   limitation d'outil). Vérification faite par inspection DOM + rendu du
   bâtiment en Python (même projection) pour confirmer la forme. La géométrie
   du bâtiment est validée visuellement hors navigateur ; le rendu live est
   validé par comptage d'éléments et finitude des coordonnées.

## Bugs trouvés et corrigés pendant la vérification

- Rendu bâtiment vide : le navigateur contrôlé ne déclenche pas
  `requestAnimationFrame` → passage à un throttle par timestamp + setTimeout ;
  et `.building-wrap { place-items:center }` réduisait le SVG à 0 px → largeur
  fixe via viewBox. Modules ES cachés → en-têtes `no-store`.
- Upload CSV : `NameError` sur la variable d'exception dans un générateur
  paresseux (message capturé avant), puis bug réel — colonnes passées en Series
  à index entier contre un index datetime → alignées en tout-NaN ; corrigé par
  `.to_numpy()` (+ `groupby(floor)` au lieu de `resample` sur index µs). Testé.

## Honnêteté sur le bâtiment

Coloration = intensité GLOBALE de l'enveloppe (une seule teinte, jamais une
façade différente d'une autre). Mention permanente : représentation à
l'échelle du volume, parois non mesurées séparément, géométrie non validée
(M6/M7). Contour extrait de l'encre vectorielle réelle du plan de rez-de-chaussée.
