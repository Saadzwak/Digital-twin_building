# Résultat exécuté — M4 multi-start uniforme

## Protocole effectivement exécuté

- 19 labels fixes, doublons conservés ; 32 départs par label, soit 608 trajectoires.
- Départ 1 : initialisation notebook (R = 0.2, C = 1e7, alpha = 1e-4).
- Départs 2–32 : tirages log-uniformes dans les bornes publiées, `numpy.random.PCG64`, graine `7096790` journalisée.
- L-BFGS-B, bornes, simulation ZOH, split, métriques et réglages par défaut inchangés.
- Sélection d’un départ par structure : minimum de MSE **train seulement**. Les valeurs validation/test sont journalisées mais ne participent pas à la sélection, y compris lorsqu’un départ est plus proche de la cible article.

## Verdict

**B — VALIDATED_INITIALIZATION_SENSITIVE.**

L’oracle des paramètres notebook reproduit RMSE validation `4.682382239968712 °C`, BIC `4578.578335283145` et RMSE test `0.8575992138865025`. La réimplémentation, les données et les métriques sont donc cohérentes avec la référence.

Le multi-start uniforme ne reproduit pas le classement BIC de l’article avec la règle train-only : le 4R3C retenu est le départ 4, avec MSE train `3.2584714171040474`, RMSE validation `5.006893630339368 °C`, BIC validation `4774.779758748735` et RMSE test `0.8494985595961497`. Le meilleur BIC parmi les départs retenus est `4738.34808036522` (LADDER_1R1C / STD_1R1C), donc le critère A est faux.

La route B est satisfaite : oracle exact, protocole identique pour les 19 labels, dispersion des 608 trajectoires documentée. Le dashboard doit afficher en permanence la sensibilité à l’initialisation et les plages empiriques de bassins. Ces plages ne sont pas des intervalles de confiance statistiques.

## Traçabilité

- Verdict et intégrité : `runs/m4/verdict.json`
- Toutes les trajectoires : `runs/m4/multistart/all_starts.json` et `.csv`
- Départs sélectionnés (train-only) : `runs/m4/multistart/selected_by_train_mse.csv`
- Dispersion par structure : `runs/m4/multistart/basin_dispersion.csv`
- Rapport lisible : `runs/m4/multistart/m4_multistart_report.md`

Le SHA-256 scellé de `all_starts.json` est `a9ba009bce9e3659d34381b336bbef363f346e4e58897de0a10b571656e56454`.
