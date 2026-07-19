# Addendum M4 — hypothèses et ambiguïtés après exécution

Ce document complète le registre validé de rétro-spécification. Il ne modifie
ni les décisions gelées ni le protocole de la cellule 55.

## H-M4-01 — Runtime notebook non épinglé

Le notebook ne journalise ni version de Python, NumPy, SciPy, BLAS/LAPACK, ni
options implicites de l’implémentation L-BFGS-B. Le runtime local exécuté est
Python 3.12.10, pandas 3.0.2 et SciPy 1.17.1. Hypothèse : le gradient numérique
et les critères d’arrêt peuvent conduire à un autre bassin local. Statut :
non résolu, priorité haute. Aucun réglage ne sera changé pour tester cette
hypothèse sans un environnement de référence autorisé.

## H-M4-02 — Agrégation M1 mémoire-bornée

Le notebook concatène les chunks capteurs avant de moyenner; la
réimplémentation conserve sommes et comptes par horodatage exact pour respecter
la mémoire. La formule est la même, mais l’ordre d’addition peut varier à
l’ulp. Statut : non résolu, priorité moyenne. Les comptes, bornes et ancres M1
sont reproduits; les paramètres notebook reproduisent aussi val/test.

## H-M4-03 — Snapshot Colab versus archive fournie

La cellule 55 ne sauvegarde pas son `df_h` d’entraînement. Les paramètres
imprimés reproduisent validation/test sur l’archive actuelle, mais la perte
train associée localement diffère du bassin obtenu par L-BFGS-B. Hypothèse : le
snapshot Colab ou les données train historiques ne sont pas strictement
identiques. Statut : non résolu, priorité moyenne.

## H-M4-04 — Précision des paramètres imprimés

Les paramètres 4R3C ne sont disponibles que dans la précision affichée du
notebook. Ils expliquent un résidu oracle d’environ 1e-6 sur les métriques,
pas l’écart local de 0.325 °C en validation. Statut : insuffisant pour expliquer
l’échec, priorité basse.

## H-M4-05 — Ré-exécution du script single-start et variance à l’ulp

Le script `scripts/run_m4_reproduction.py` restauré (2026-07-19) a ré-exécuté
les 19 fits single-start sur les mêmes données (`hourly_reference.csv`
inchangé, hash `9b70de93…` vérifié avant/après), le même code
(`reproduction.py` non modifié depuis le run initial) et les mêmes
bibliothèques (installées en avril, aucun changement entre les deux runs).
Toutes les valeurs reproduisent l’historique à 12 décimales imprimées, mais
pas bit à bit : par exemple RMSE validation 4R3C `5.007034573211701` contre
`5.007034573212` journalisé historiquement, soit un écart d’environ 3e-13 °C
(quelques ulp). Cause exacte non identifiée ; aucun des facteurs vérifiables
(code, données, bibliothèques) ne diffère aujourd’hui. Décisions prises :

- `runs/m4/single_start_verdict.json` (intact depuis le run initial) reste la
  référence historique scellée ; son SHA-256
  `e8bd817d5bc522bd38b664204eb2dbdb7c173dd761c3996f783397e934198752` est
  désormais épinglé par le test d’artefact.
- `runs/m4/reproduction_19_models.csv` et `.json` sont la sortie journalisée
  de la ré-exécution ; le test les compare aux valeurs historiques scellées
  avec une tolérance explicite de 1e-9 (niveau ulp, documentée), au lieu d’une
  égalité bit à bit impossible à garantir entre exécutions.
- Aucun chiffre produit n’est affecté : le run single-start est étiqueté
  `FAILED_REPRODUCTION_DO_NOT_USE_FOR_PRODUCT_CLAIMS` et la chaîne produit ne
  lit que les artefacts multi-start scellés par hash.

Statut : écart documenté, non masqué ; priorité basse (sans effet aval).

## Conséquence de produit

Le run local M4 est invalide. Tous les modules aval requièrent
`runs/m4/verdict.json` avec `validated=true`; l’état présent refuse plutôt que
de convertir ces hypothèses en résultats utilisateur.
