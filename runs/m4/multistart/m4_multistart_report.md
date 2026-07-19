# M4 — rapport de dispersion multi-start

Verdict : **B** — VALIDATED_INITIALIZATION_SENSITIVE.

Les redémarrages sont retenus exclusivement par MSE train. Les valeurs validation/test ci-dessous sont rapportées après coup ; elles n’ont servi à choisir aucun redémarrage.

## Classement des structures retenues

| Rang BIC validation | Structure | Départ retenu | MSE train | RMSE validation | BIC validation | RMSE test | statut |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | LADDER_1R1C | 29 | 3.25845115 | 5.006916 | 4738.348080 | 0.849494 | success=True |
| 2 | STD_1R1C | 29 | 3.25845115 | 5.006916 | 4738.348080 | 0.849494 | success=True |
| 3 | STD_2R1C_parallel_losses | 14 | 3.25846604 | 5.007003 | 4745.688130 | 0.849592 | success=True |
| 4 | LADDER_2R2C | 3 | 3.2584668 | 5.006901 | 4752.917401 | 0.849500 | success=True |
| 5 | STD_2R2C_air_mass | 3 | 3.2584668 | 5.006901 | 4752.917401 | 0.849500 | success=True |
| 6 | STD_3R2C_air_shunt | 31 | 3.25848343 | 5.006887 | 4760.198195 | 0.849500 | success=True |
| 7 | LADDER_3R3C | 11 | 3.25845605 | 5.006929 | 4767.511672 | 0.849512 | success=True |
| 8 | STD_3R3C_two_masses_series | 11 | 3.25845605 | 5.006929 | 4767.511672 | 0.849512 | success=True |
| 9 | STD_4R3C_two_masses_plus_air_shunt | 4 | 3.25847142 | 5.006894 | 4774.779759 | 0.849499 | success=True |
| 10 | STD_5R3C_air_shunt_mid_shunt | 23 | 3.25848061 | 5.006696 | 4781.952922 | 0.849334 | success=True |
| 11 | LADDER_4R4C | 21 | 3.2585118 | 5.006951 | 4782.102222 | 0.849522 | success=True |
| 12 | STD_6R4C_three_masses_plus_shunts | 15 | 3.25845708 | 5.006920 | 4796.662126 | 0.849498 | success=True |
| 13 | LADDER_5R5C | 22 | 3.25845456 | 5.006950 | 4796.679338 | 0.849519 | success=True |
| 14 | STD_7R5C_four_masses_plus_shunts | 24 | 3.25847939 | 5.006900 | 4811.228376 | 0.849486 | success=True |
| 15 | LADDER_6R6C | 21 | 3.25846572 | 5.006915 | 4811.237143 | 0.849490 | success=True |
| 16 | LADDER_7R7C | 4 | 3.25849775 | 5.006930 | 4825.823560 | 0.849503 | success=True |
| 17 | LADDER_8R8C | 2 | 3.25845613 | 5.006849 | 4840.353723 | 0.849433 | success=True |
| 18 | LADDER_9R9C | 1 | 3.25865671 | 5.006953 | 4854.992619 | 0.849525 | success=True |
| 19 | LADDER_10R10C | 1 | 3.25848065 | 5.006928 | 4869.556193 | 0.849502 | success=True |

## 4R3C et cible article/notebook

Cible oracle indépendante : RMSE validation 4.682382 °C ; BIC 4578.578337 ; RMSE test 0.857599 °C.
Départ 4R3C le plus proche en RMSE validation (non retenu par ce critère) : start 12, RMSE 4.702299, BIC 4591.006464, test 0.966587, MSE train 3.58336053.

Ce rapprochement est descriptif seulement. Même s’il était proche de la cible, il ne peut pas remplacer le départ retenu sans violer la règle de sélection train.

## Interprétation de la dispersion

Les q05–q95 et fractions de départs proches du meilleur sont des plages empiriques de la banque fixée. Elles ne sont pas des intervalles de confiance statistiques ni une cartographie exhaustive des bassins.
