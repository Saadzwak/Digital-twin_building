# Addendum M4 multi-start — hypothèses et limites

## H-M4-MS-01 — Taille de banque et seuil de classement

Le notebook ne définit ni nombre de redémarrages ni seuil « écart net ».
Décision de projet pré-déclarée : 32 départs, graine 7096790 et marge BIC de
10.0 pour la route A. Ces choix ne proviennent pas de l’article et ne sont pas
ajustés après lecture des résultats. Ils mesurent une sensibilité échantillonnée
et ne prouvent pas que tous les bassins possibles ont été explorés.

## H-M4-MS-02 — Plages inter-départs

Les q05–q95 de MSE et BIC entre redémarrages ne sont pas des intervalles de
confiance statistiques : les trajectoires partagent les mêmes données et le
protocole n’échantillonne pas une population expérimentale. L’interface les
nomme explicitement « dispersion empirique des initialisations ».

## H-M4-MS-03 — Classement à deux niveaux

Le redémarrage est choisi par MSE train, puis les structures sont comparées par
BIC validation. Cette séparation suit l’autorisation de produit ; elle peut
retenir un départ moins bon en validation qu’un autre départ de la même
structure. Ce dernier reste journalisé mais n’est jamais substitué.

## H-M4-MS-04 — M7 géométrique

Les plans attendent une validation humaine de frontière, échelle, nord et
hauteur. Avant celle-ci, aucun métrique géométrique ni ajustement contraint ne
est produit. Quand elle est disponible, la règle est `R_i = r'' / A_i` avec un
seul `r''` libre ; aucune résistance par façade n’est déclarée identifiée.
