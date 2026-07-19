# Protocole du produit de démonstration en direct

Ce document fixe les choix du pipeline produit (`live_run.py`) et les sépare
explicitement du protocole gelé de reproduction M4, qui reste inchangé.

## Banc en direct (étape 3 de l'exécution visible)

- Mêmes 19 étiquettes de structures, mêmes bornes, même appel L-BFGS-B sans
  option, même générateur de départs (PCG64, graine 7096790) que le protocole
  scellé — mais **3 départs** par structure au lieu de 32, pour tenir dans une
  démonstration de quelques minutes. Les départs 2 et 3 sont, par profil de
  paramètres, exactement les départs 2 et 3 de la banque scellée.
- La perte utilise le **simulateur modal accéléré** (`fast_sim.py`), testé
  équivalent à la boucle gelée à moins de 1e-7 °C sur les 19 structures
  (test `test_fast_sim.py`). La trajectoire d'optimisation peut donc différer
  du protocole gelé au niveau des ulp ; c'est journalisé, pas caché.
- **Règle d'admissibilité** : une structure dont la meilleure MSE
  d'entraînement dépasse 2× la médiane du banc est écartée du classement et
  affichée comme telle. Motif : avec peu de départs, certaines structures
  restent dans un bassin dégénéré (ex. LADDER_5R5C, MSE train ≈ 43 contre
  ≈ 3,26) dont le BIC de validation serait pourtant le meilleur par accident ;
  la présenter comme « retenue » serait trompeur. La règle est uniforme,
  déclarée avant sélection et visible dans l'interface.
- Sélection inchangée sur les admissibles : par structure, MSE train
  minimale ; entre structures, BIC validation minimal.

## Jumeau d'exploitation (dérive, scénarios, indicateurs)

Sur le jeu de référence, le jumeau est la **paramétrisation 4R3C publiée par
l'article**, reproduite par l'oracle à 1e-6 (validation 4,682 °C, test
0,858 °C). Motif, affiché dans l'interface : la re-identification automatique
converge vers des solutions « volant thermique » sans lecture physique
(constante de temps ≈ 1,6 milliard d'heures, couplage enveloppe ≈ 0,001 W/K),
sur lesquelles tout scénario paramétrique produit un effet nul. Le banc en
direct reste affiché comme mesure de sensibilité (verdict B maintenu).

Sur un CSV déposé, aucune référence publiée n'existe : le jumeau est la
sélection du banc, et les indicateurs non lisibles physiquement le disent.

L'incertitude des scénarios et du niveau de déperdition est la **plage entre
calages indépendants du même comportement** : le vecteur publié plus les
départs scellés du 4R3C dont la RMSE de validation est à moins de 0,25 °C de
l'oracle (départs 2 et 12). Cette plage sous-estime l'incertitude totale et
l'interface le dit.

**Constat exécuté sur cette plage** : la valeur absolue du niveau de
déperdition n'est pas robuste — les calages équivalents impliquent des UA
effectifs de 63 à ≈ 6 131 W/°C (facteur ≈ 97). En revanche, l'effet
énergétique des scénarios reste concordant en signe et en ordre de grandeur
(enveloppe ×2 : −14,5 à −6,3 % selon le calage). Le produit affiche donc le
niveau absolu comme « non robuste entre calages » (drapeau
`robust_between_calibrations`, testé) et présente les scénarios avec leur
fourchette inter-calages.

## Dérive annuelle

Simulation en boucle ouverte sur l'année complète (comme la figure annuelle
de l'article). Bande calibrée = médiane ± 3 écarts robustes (1,4826 × MAD)
des moyennes journalières de la période de calage ; **rupture** = première
sortie persistante de 14 jours ; **début du glissement** = début de
l'excursion |z| > 1 contiguë qui mène à la rupture. Sur le jeu de référence :
glissement dès le 2021-10-03, rupture le 2021-11-15, −10,4 °C ensuite,
écart cumulé ≈ −18 800 °C·h. Les seuils n'ont pas été ajustés pour viser une
date ; le test `test_annual_drift.py` épingle le résultat.

## Scénarios

Interventions sur les paramètres identifiés uniquement (jamais sur les
forçages) : résistances vers l'extérieur ×1,5 et ×2, résistance du chemin
direct intérieur-extérieur ×2, capacités ×1,5. Deux effets par scénario :
température libre à consommation mesurée identique, et énergie nécessaire à
confort identique obtenue en **inversant exactement le nœud d'air** du modèle
discret (identité vérifiée par test : paramètres inchangés → puissance
mesurée retrouvée à 1e-4 W). Un effet sous 0,05 °C ou 0,5 % est annoncé
« négligeable » au lieu d'être affiché en notation scientifique. Un scénario
non interprétable (inertie sur masses quasi intégratrices) est déclaré tel
quel avec son motif.

## Langage de surface

La surface n'utilise aucun terme d'identification (liste gardée par test dans
`business_language.py`) ; le détail méthodologique replié conserve la rigueur
complète, y compris le verdict B et les chemins des artefacts scellés.

## Interface salle de contrôle et cohérence sélection↔jumeau (2026-07-19)

L'interface produit est `webapp/` (FastAPI + SPA sombre, bâtiment 3D SVG
axonométrique réactif, topologie RC animée). Le banc de référence est
**précalculé une fois** puis rejoué à cadence accélérée (~34 s), badgé
« replay d'un calcul réel » à l'écran.

Cohérence banc↔jumeau : l'en-tête affiché est toujours la structure
effectivement utilisée comme jumeau. Sur la référence, l'identification
automatique est dégénérée — les départs 4R3C au meilleur RMSE validation ont
un calage d'entraînement ruiné (train ≈ 41,7) et un UA non physique (10⁶–10⁸
W/K), tandis que le train-best est le bassin générique ; seule la calibration
publiée donne un UA physique (63 W/K). Le banc ne peut donc pas sélectionner un
jumeau physique. L'en-tête montre donc la structure de référence (4R3C = le
jumeau), et la sélection automatique du banc (LADDER_1R1C) est **surfacée et
déclarée** (champ `selection.bank_auto_pick`, `twin.consistent_with_selection`),
jamais masquée.

Rendu : charts SVG maison (plus de Vega) ; chaque réponse API passe par
`sanitize.clean` (aucun NaN/Inf ne peut atteindre le client). Le bâtiment est
extrait de l'encre vectorielle du plan de rez-de-chaussée
(`building_geometry.py`, artefact `runs/geometry/building_massing.json`) ;
coloration = intensité GLOBALE de l'enveloppe, échelle du volume, parois non
mesurées séparément, géométrie non validée.
