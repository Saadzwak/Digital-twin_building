# M4 — matrice de comparaison ligne à ligne avec la cellule 55

Ce document est un diagnostic préparé avant verdict. Il rend visible chaque
traduction de la cellule 55 dans la réimplémentation afin que tout écart de
reproduction puisse être attribué sans modifier le protocole.

| Bloc cellule 55 | Réimplémentation | État de comparaison | Écart potentiel à auditer si M4 échoue |
|---|---|---|---|
| `df_h.copy().dropna(...).sort_index()` puis mois UTC | `reference_ingestion.split_reference_months` | mêmes trois colonnes et split calendrier | CSV intermédiaire M1 et index pandas ; vérifier hashes et ancres |
| `DT = 3600.0` | `identification.DT_SECONDS` | 3 600 s fixe | aucun dt variable n’est introduit |
| `rmse`, `mae`, RSS/AIC/BIC | `calculate_metrics` | même formule ; résidu stocké mesuré − estimé | signe de perte au carré neutre, mais résidu affiché est désormais gelé |
| `build_graph_matrices` : laplacien, `Cinv @ K` | `rc_core.build_continuous_matrices` | mêmes boucles et mêmes signes | ordre/association flottante et BLAS |
| matrice augmentée `expm(M*dt)` | `rc_core.discretize_exact` | mêmes blocs et mêmes colonnes entrée | version SciPy / LAPACK |
| `x[0,:] = Tin0`; `Tout[k]`, `Q[k]` | `rc_core.simulate_open_loop` | même rollout ouvert ZOH | aucune assimilation, aucun pas réel variable |
| `make_ladder` et 9 définitions STD | `topologies.reference_model_bank` | 19 labels conservés, 3 doublons signalés | vérifier l’ordre des indices 4R3C par oracle M2 |
| `x0`, `bounds`, `minimize(..., method='L-BFGS-B')` | `identification.fit_topology` | mêmes valeurs, aucun `options`, aucun multistart | comportement numérique SciPy et gradient numérique par défaut |
| `eval_model` validation/test initialisés séparément | `evaluate_topology` | même état initial propre à chaque segment | aucune fuite train/val/test |
| boucle `rows`, même `k=nR+nC+1` | `reproduction.run_reproduction` | statut, métriques et doublons non filtrés | aucun tri/écrasement des labels |
| sortie BIC brute + affichage | `reproduction.write_reproduction_artifacts` | brute journalisée, affichage prévu à une décimale | ne pas tester sur une valeur déjà arrondie |

## Différences délibérées déjà connues, sans correction de résultat

1. **Chemin source.** L’archive fournie contient `Data_Nature/data`, pas le
   chemin Colab `raw_data` ; la résolution est documentée dans
   `data_path_resolution.md`.
2. **API pandas.** `resample("1H")` est refusé sous pandas 3 ; `"1h"` est
   sémantiquement identique et journalisé.
3. **Mémoire Tin.** Le notebook concatène les chunks capteurs avant la moyenne.
   La réimplémentation accumule somme et nombre par horodatage pour ne pas
   dépasser la mémoire. Elle conserve la formule de moyenne mais peut changer
   l’ordre d’addition à l’ulp près.
4. **Versions de runtime.** Le notebook ne fige ni pandas ni SciPy ; le run
   local utilise Python 3.12.10, pandas 3.0.2 et SciPy 1.17.1. L-BFGS-B peut
   donc suivre une trajectoire numérique différente sans changement de code.

## Règle de diagnostic

Si M4 ne satisfait pas le 4R3C exact, cette matrice est utilisée dans cet ordre
pour comparer : données finales, matrices 4R3C, un rollout avec paramètres
notebook, initialisation/bornes, statut/itérations L-BFGS-B, puis version de
runtime. Aucune borne, initialisation, paramètre ou donnée n’est ajusté afin de
faire coïncider une sortie.
