# M4 — protocole multi-start pré-déclaré

Ce protocole conserve strictement la simulation et l’identification de la
cellule 55. Il ne modifie que le point initial de L-BFGS-B sur le problème
non convexe.

## Banque commune

- 19 labels, doublons compris ; aucun label n’est supprimé.
- 32 départs par label : le départ 1 du notebook, puis 31 tirages.
- Départ 1 : `R=0.2`, `C=1e7`, `alpha=1e-4` en unités physiques.
- Départs 2–32 : uniforme dans les bornes gelées de l’espace logarithmique,
  donc log-uniforme en unités physiques.
- Graine racine `7096790`, générateur explicite `numpy.random.PCG64`.
- Les labels de même profil `(n_R, n_C)` reçoivent la même banque, mais sont
  exécutés et journalisés séparément.
- Bornes, `method='L-BFGS-B'`, tolérances implicites et itérations implicites
  ne changent pas. Aucun paramètre oracle n’entre dans la banque.

## Sélection et journalisation

Pour une structure, le fit retenu est celui de MSE train finie minimale, avec
départage par identifiant de départ croissant. Un `success=False` à MSE finie
reste éligible et son statut est conservé. Validation et test sont calculés
pour journaliser la dispersion, jamais pour choisir le redémarrage.

Entre structures, le classement utilise le BIC validation des seuls fits déjà
retenus par MSE train. Tous les départs, leurs paramètres initiaux/finals,
statuts, MSE, RMSE et BIC sont archivés sous `runs/m4/multistart/`.

## Verdict M4

Route A : `STD_4R3C` a le BIC validation strictement minimal et l’écart avec
la deuxième structure est au moins 10.0 BIC bruts. Ce seuil de séparation
forte est défini avant l’exécution.

Route B : l’oracle des paramètres imprimés du notebook reproduit les trois
métriques cibles, les `19 × 32` tentatives sont complètes et homogènes, et la
dispersion empirique est écrite. La route B active un bandeau permanent de
sensibilité à l’initialisation ; elle ne transforme pas la dispersion en
intervalle de confiance statistique.

## Artefacts

- `protocol.json` : graine, versions, hash CSV, règles et bornes.
- `starts.csv`, `all_starts.csv`, `all_starts.json` : tentatives complètes.
- `selected_by_train_mse.csv` : une sélection train par label.
- `basin_dispersion.csv` et `.md` : q05/médiane/q95 empiriques et indicateur.
- `notebook_parameter_oracle.json` : test indépendant, hors sélection.
- `runs/m4/verdict.json` : route A, B ou échec.
