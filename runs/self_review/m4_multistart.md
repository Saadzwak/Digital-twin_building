# Auto-critique hostile — M4 multi-start

Date d’exécution : 2026-07-18. Artefact scellé : `runs/m4/verdict.json` ; SHA-256 de `all_starts.json` : `a9ba009bce9e3659d34381b336bbef363f346e4e58897de0a10b571656e56454`.

## Verdict exécuté

Route **B** validée, et non route A. Les 19 labels fixes ont chacun reçu exactement 32 départs (608 paires structure/départ uniques), avec graine PCG64 `7096790`. Le redémarrage retenu pour chaque structure est le minimum de MSE train uniquement. L’oracle injecté séparément reproduit la cible notebook à 1e-6, tandis que le 4R3C retenu par train donne RMSE validation `5.006893630339368`, BIC `4774.779758748735`, test `0.8494985595961497`.

## Critique adversariale et corrections

1. **Quelle affirmation ne survivrait pas à un examen ?**
   Dire que les 32 départs « trouvent le meilleur bassin » ne survivrait pas : ils ne constituent ni une recherche exhaustive ni une preuve d’unicité. **Correction :** le verdict est B, le produit dit explicitement « sensible à l’initialisation » et ne revendique pas le classement de l’article.

2. **Quel chiffre est affiché sans son incertitude ?**
   Les BIC et RMSE de chaque départ sont des observations ponctuelles. **Correction :** les q05–q95 empiriques de MSE train et BIC validation, le nombre de départs finis et la fraction proche du meilleur sont publiés dans `basin_dispersion.csv`; ils sont qualifiés comme dispersion inter-départs, pas comme IC statistique.

3. **Quelle hypothèse est enterrée dans le code ?**
   La banque a `N=32`, graine `7096790`, et le seuil de séparation BIC A vaut 10. **Correction :** ces trois choix sont écrits avant agrégation dans `docs/m4_multistart_protocol.md`, `protocol.json`, `verdict.json` et la documentation des ambiguïtés. Le point 1 reste exactement l’initialisation notebook, les autres sont log-uniformes dans les bornes gelées.

4. **Qu’est-ce qui marche uniquement sur ce jeu de données précis ?**
   La dispersion et le bassin retenu sont propres aux signaux PLEIAData, au split 6460/1464/680 et à la période étudiée. **Correction :** les artefacts portent ces provenances ; aucune conclusion de transférabilité bâtiment/jeu de données n’est produite.

5. **Où ai-je écrit « ça marche » sans l’avoir exécuté ?**
   Nulle part pour M4 : les trois shards, l’agrégation, l’oracle et le rapport ont été exécutés. **Correction apportée avant passage à M5 :** le verdict scelle les hashes des 608 trajectoires et l’accès aval vérifie ce scellement au lieu de faire confiance à un booléen isolé.

## Fait sensible à ne pas maquiller

Le départ 4R3C le plus proche de la validation oracle est le départ 12 (`RMSE validation 4.702299`, `BIC 4591.006464`), mais sa MSE train `3.58336053` est nettement plus élevée que celle du départ 4 retenu (`3.25847142`). Il est conservé comme diagnostic descriptif et n’est jamais substitué au départ sélectionné.
