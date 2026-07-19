# Hypothèses, divergences et ambiguïtés — rétro-spécification

Statut : registre factuel en attente de décision utilisateur. Les éléments ci-dessous sont documentés, pas résolus.

## A. Comportements issus du notebook mais absents ou insuffisamment spécifiés dans l'article RC

| ID | Comportement de référence notebook | Source notebook | Statut |
|---|---|---|---|
| N-01 | Le compteur choisi est fixé par la constante METER_A_ID = 335546926. | cellules 16, 20, 55 | divergence de bloc documentée ci-dessous |
| N-02 | V22 est traitée comme une énergie cumulée, différenciée puis divisée par la médiane globale 599.016 s pour former Qhvac_W_A. | cellules 16, 20 | non décrit dans l'article RC |
| N-03 | Qhvac_W_A est winsorisée aux quantiles 0.001 et 0.999 avant la fusion. | cellule 20 | non décrit dans l'article RC |
| N-04 | Tous les horodatages sont forcés en UTC, y compris la météo dépourvue d'offset explicite. | cellules 16, 18, 20 | non décrit dans l'article RC |
| N-05 | Tout et Qhvac_W_A sont interpolées sur toute l'année avant tout split ; Tin ne l'est pas. | cellule 20 | non décrit dans l'article RC |
| N-06 | Le resampling horaire est une moyenne sur les points disponibles, puis les heures incomplètes sont supprimées sans réindexation. | cellule 20 | explique les 8 604 échantillons |
| N-07 | Tous les états, y compris les masses, sont initialisés à la première Tin mesurée de chaque période. | cellule 55 | absent de l'article |
| N-08 | Les entrées sont maintenues constantes sur un pas via une exponentielle de matrice augmentée. | cellule 55 | Bd non détaillé dans l'article |
| N-09 | Validation et test sont des rollouts ouverts séparés, chacun réinitialisé par sa première Tin mesurée. | cellule 55 | absent de l'article |
| N-10 | Les résultats sont conservés même lorsque res.success vaut False. | cellule 55 | l'article ne donne pas ces statuts |
| N-11 | Les 19 labels incluent des doublons mathématiques : LADDER_1R1C = STD_1R1C, LADDER_2R2C = STD_2R2C_air_mass, LADDER_3R3C = STD_3R3C_two_masses_series. | cellule 55 | la présentation les compte néanmoins comme candidats distincts |

## B. Divergences confirmées

### B-01 — Bloc A pour Tin, compteur B pour Qhvac

Le notebook sélectionne les capteurs de BLOCK = A, mais fixe METER_A_ID à 335546926.

Le Data Descriptor PLEIAData indique explicitement :

| Bloc selon l'article PLEIAData | IDdevice V22 |
|---|---|
| A | 335546928 |
| B | 335546926 |
| C | 335546927 |

Le run de référence associe donc, selon la source PLEIAData, Tin du bloc A à la consommation du bloc B. Ce conflit est direct et n'est pas corrigé ici.

### B-02 — Archive fournie et chemins du notebook

Copie_de_BDTA.ipynb attend Data_Nature/raw_data. Data_Nature.zip contient Data_Nature/data, avec les fichiers bruts et des fichiers déjà traités. Le notebook ne se lance donc pas directement contre l'archive fournie sans résoudre le chemin.

### B-03 — Version et période des données

- Le Data Descriptor annonce une période du 1er janvier au 18 décembre 2021.
- Les sorties du notebook montrent capteurs et consommation jusqu'au 31 décembre 2021, ainsi que MU62 jusqu'au 20 février 2022.
- La référence PLEIAData de l'article source cite Zenodo 10.5281/zenodo.7620136 ; le cadrage de ce projet indique 10.5281/zenodo.7096790.

Ces indices signalent une différence de version ou de packaging, non résolue.

### B-04 — Schéma et métadonnées de l'archive versus Data Descriptor

| Sujet | Data Descriptor | Archive / notebook |
|---|---|---|
| relations-sensor et relations-hvac | quatre colonnes : ID, desc, block, room | trois colonnes : ID, block, room |
| relations-hvac | 86 lignes annoncées | 87 lignes observées |
| data-hvac | V4, V5, V12, V26 documentées | V6 est aussi présente et lue, mais non utilisée dans le run final |
| MU62 | noms et formats décrits comme hour, pred, vvnax, %d%m%y | fichier lu : hora, prec, vvmax, exemples 01/01/21 et 00:10:00 |

### B-05 — Préparation PLEIAData versus préparation du notebook projet

Le Data Descriptor recommande notamment de remplacer les V2 intérieures inférieures à 0 °C ou supérieures à 60 °C par la dernière valeur valide, et décrit un traitement consommation à 60 minutes avec dif_cons, filtrage et lissage.

Le notebook projet :

- ne fait pas ce remplacement V2 ;
- différencie V22 à la cadence brute ;
- applique une conversion en W avec un pas médian ;
- winsorise seulement les extrêmes 0.1 % et 99.9 %.

Le protocole de référence est celui du notebook, mais il ne faut pas le présenter comme la préparation prescrite par le Data Descriptor.

### B-06 — Figure 4R3C, ordre des états et capacités

La figure de l'article présente Ext–R1–Tm1–R2–Tm2–R3–Tair avec C1 sur Tm1, C2 sur Tm2, C_air sur Tair et un shunt R4 Ext–Tair.

Le notebook emploie air–R0–M1–R1–M2–R2–Ext, plus R3 air–Ext, avec C0 sur air, C1 sur M1 et C2 sur M2. Les graphes sont isomorphes après renommage, comme documenté dans protocol_reference.md.

Cependant, la sortie du modèle de référence donne :

~~~text
C0 sur air = 1.74260153e10
C1 sur M1  = 2.98095799e3
C2 sur M2  = 6.34499651e10
~~~

Cela ne soutient pas directement l'énoncé de la présentation selon lequel la capacité d'air serait la petite capacité. La consigne utilisateur est de suivre la figure pour les capacités, et non le texte de la présentation ; aucune relabellisation ni interprétation corrective n'est appliquée ici.

### B-07 — Les valeurs brutes et l'intervalle affiché des 18 autres modèles

La présentation affiche une plage 4.98–5.02 °C pour les 18 modèles non retenus. Dans la cellule 55 :

| Modèle | RMSE brute | Arrondi à deux décimales |
|---|---:|---:|
| STD_3R2C_air_shunt | 4.975361 | 4.98 |
| STD_6R4C_three_masses_plus_shunts | 5.022779 | 5.02 |

Les 18 valeurs entrent dans la plage seulement après affichage à deux décimales. Les résultats bruts doivent rester journalisés.

### B-08 — Statut de convergence

La cellule 55 enregistre res.success = False pour LADDER_2R2C et STD_2R2C_air_mass, tout en reportant leurs métriques. L'article et la présentation présentent le banc comme évalué, sans exposer ces deux statuts. Le message détaillé de scipy n'est pas conservé dans la sortie du notebook.

### B-09 — Notebook à plusieurs expérimentations

Le même fichier contient plusieurs protocoles incompatibles avec le run de référence :

| Cellules | Protocole / résultat | Relation au run de référence |
|---|---|---|
| 22 | 10 ladders, split chronologique 70/30, RMSE autour de 8.81 | essai antérieur |
| 29 | 1R1C avec entrée HVAC enrichie et intégration Euler, RMSE validation 13.16 | essai antérieur |
| 30 | 15 modèles, split 70/30 | essai antérieur |
| 32 | 19 modèles, split 60/20/20, meilleur LADDER_5R5C | essai antérieur |
| 36 | split saisonnier 60/20/20 | essai exploratoire |
| 54 | modèle HVAC-rich avec alpha, beta, gamma, delta et régularisation ; erreur NameError | non exécuté avec succès |
| 55 | split Jan–Sep / Oct–Nov / Déc., 19 modèles, résultats publiés | référence candidate |

La cellule 55 est retenue uniquement parce que ses sorties correspondent exactement aux chiffres de l'article, pas parce que le notebook rend l'ordre des expérimentations explicite.

### B-10 — Biais potentiel de préparation avant split

L'interpolation de Tout et Qhvac_W_A est effectuée sur l'année entière avant la séparation mensuelle. En cas de trou chevauchant une frontière train/validation/test, elle peut utiliser une information temporellement future. L'article affirme l'absence de fuite temporelle ; le notebook ne contrôle pas ce cas.

### B-11 — Convention de signe du résidu

La cellule 45 définit erreur = Tin_mesuree - Tin_estimee. Les cellules 59 et 62 définissent erreur = Tin_estimee - Tin_mesuree. L'article décrit une distribution à asymétrie positive sans fixer cette convention. Aucun choix n'est appliqué ici.

## C. Ambiguïtés restant après lecture complète

1. La valeur de METER_A_ID doit-elle être conservée pour reproduire strictement le notebook, ou corrigée selon la cartographie officielle des blocs ? Cette décision modifierait les résultats et n'est pas prise.
2. MU62 est-elle horodatée en temps local espagnol ou déjà en UTC ? Le notebook force utc=True sur une chaîne sans offset.
3. V22 est-elle garantie cumulative, et comment gérer resets, valeurs négatives ou pas de durée irrégulier ? Le notebook applique une constante médiane sans règle de contrôle supplémentaire.
4. Quel snapshot Zenodo exact est la référence, et faut-il utiliser le répertoire data ou raw_data ? Les documents fournis ne permettent pas de le trancher.
5. Quelle version de NumPy, SciPy et pandas a produit la cellule 55 ? Le notebook ne les fige pas et ne renseigne pas les options effectives par défaut de L-BFGS-B.
6. Quel sens doit recevoir le statut scipy False des deux modèles 2R2C lors du futur test d'acceptation : résultat exploitable, convergence partielle ou échec ? Le notebook ne le définit pas.
7. Faut-il qualifier les trois doublons de la banque comme structures distinctes, malgré leur équivalence mathématique, afin de conserver strictement les 19 lignes du notebook ? Le protocole les conserve mais ne tranche pas l'interprétation.
8. La figure 4R3C fixe la connectivité et l'emplacement des capacités, mais le rôle physique des capacités identifiées est contradictoire avec le texte de la présentation. Il faut conserver le mapping de figure sans lui attribuer une signification de paroi non justifiée.

## D. Décisions déjà fixées par l'utilisateur

- Aucune borne, initialisation ou autre paramètre ne sera ajusté pour forcer une reproduction.
- Le BIC sera testé à une décimale pour l'affichage ; sa valeur brute sera journalisée.
- La figure 4R3C prévaut sur le texte de la présentation pour l'emplacement des capacités.
- Les plans restent hors du module de reproduction jusqu'à validation explicite.

