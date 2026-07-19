# Référence de protocole — rétro-spécification du notebook

Statut : brouillon de rétro-spécification, en attente de validation utilisateur.

Périmètre : ce document décrit le comportement effectivement exécuté par la cellule 55 de Copie_de_BDTA.ipynb. Cette cellule est retenue comme candidat de référence car sa sortie reproduit les tailles de splits et les chiffres publiés. Les cellules antérieures sont des essais historiques et ne doivent pas être mélangées à ce protocole.

## Sources et hiérarchie

1. Source opérationnelle : Copie_de_BDTA.ipynb, cellule 55, et les cellules de préparation 6, 8, 11, 16, 18 et 20.
2. Source de comparaison scientifique : ID_395__Springer_(1) (1).pdf et Presentation_ ID 395.pdf.
3. Source de métadonnées PLEIAData : s41597-023-02023-3.pdf.
4. Les écarts et choix non arbitrés sont consignés dans hypotheses_et_ambiguities.md. Aucun n'est corrigé dans cette spécification.

## 1. Jeu de données effectivement construit

### 1.1 Fichiers et colonnes utilisés par le notebook

Le notebook attend initialement le répertoire Colab suivant :

~~~text
/content/pleiadata/Data_Nature/raw_data/
  data-sensor.csv
  data-cons.csv
  data-hvac.csv
  relations-sensor.csv
  relations-hvac.csv
  MU62_dm.txt
~~~

Le run de référence n'utilise dans le modèle final que les trois colonnes horaires ci-dessous :

| Série finale | Source notebook | Transformation effective |
|---|---|---|
| Tin | data-sensor.csv : IDdevice, Date, V2 | moyenne des valeurs V2 des capteurs dont block = A |
| Tout | MU62_dm.txt : fecha, hora, tmed | tmed, converti en index temporel UTC |
| Qhvac_W_A | data-cons.csv : IDdevice, Date, V22 | différence de V22, conversion en W puis winsorisation |

La branche HVAC-rich lit aussi V4, V5, V6, V12 et V26 de data-hvac.csv, mais elle n'est pas exécutée dans le protocole de référence de la cellule 55.

### 1.2 Sélection et agrégation Tin

1. BLOCK est fixé à A.
2. relations-sensor.csv est lu avec le séparateur point-virgule.
3. Les identifiants dont la colonne block vaut A sont sélectionnés. La sortie enregistrée indique 49 capteurs.
4. data-sensor.csv est lu par blocs de 1 000 000 lignes avec les colonnes IDdevice, Date et V2.
5. Date est convertie avec utc=True ; V2 est convertie en numérique ; les lignes sans Date ou V2 sont supprimées.
6. Tin est calculée par moyenne de V2 pour chaque horodatage exact, puis triée.

La moyenne horaire est effectuée plus loin, après jointure avec Tout et Qhvac_W_A. Le notebook ne repondère pas les capteurs par volume, surface ou localisation.

### 1.3 Construction de Qhvac_W_A

Le run de référence fixe METER_A_ID à 335546926.

1. data-cons.csv est lu avec le séparateur point-virgule.
2. IDdevice est converti en texte, Date avec utc=True et V22 en numérique ; les lignes invalides sont supprimées.
3. Seules les lignes du compteur fixé sont conservées et triées.
4. V22 est moyenné par horodatage exact et nommé E_cum_kWh dans le notebook.
5. E_diff est la différence première de cette série ; sa première ligne est supprimée.
6. Le pas est une constante : médiane des écarts entre horodatages de E_diff. La sortie de la cellule 20 donne 599.016 secondes.
7. Qhvac_W_A = E_diff × 3.6e6 / 599.016.
8. Cette série est bornée aux quantiles 0.001 et 0.999. La sortie enregistrée donne environ 234.760 à 14527.372 W.

Cette construction est un comportement de référence du notebook. Le sens physique de V22, le choix du compteur et la gestion des éventuels resets restent traités dans hypotheses_et_ambiguities.md.

### 1.4 Construction de Tout

1. MU62_dm.txt est lu avec le séparateur point-virgule.
2. Les espaces des noms de colonnes sont supprimés.
3. fecha et hora sont concaténées, puis lues avec le format %d/%m/%y %H:%M:%S et utc=True.
4. Les dates invalides sont supprimées, l'index est trié, et tmed est convertie en numérique.
5. Tout est la série tmed non nulle.

### 1.5 Fusion, interpolation, resampling et manquants

1. Tin, Tout et Qhvac_W_A sont concaténées sur l'union de leurs horodatages exacts.
2. Tout et Qhvac_W_A sont interpolées dans le temps sur l'intégralité de la série, avant le split.
3. Les lignes sans Tin sont supprimées ; Tin n'est pas interpolée.
4. Chaque colonne est moyennée avec resample 1H.
5. Les heures contenant une valeur manquante dans au moins une des trois séries sont supprimées.
6. Aucune grille horaire complète n'est créée : les heures manquantes restent absentes.

La sortie de référence est df_h, 8 604 lignes, de 2021-01-01 00:00:00+00:00 à 2021-12-31 22:00:00+00:00.

## 2. Découpage chronologique effectif

Dans la cellule 55, df_h est trié et filtré sur Tin, Tout et Qhvac_W_A non nuls. Le split est défini par le mois de l'index UTC :

| Sous-ensemble | Mois | Bornes visibles dans la sortie | Nombre d'échantillons |
|---|---|---|---:|
| Entraînement | janvier à septembre | 2021-01-01 00:00 à 2021-09-30 23:00 UTC | 6 460 |
| Validation | octobre et novembre | 2021-10-01 00:00 à 2021-11-30 23:00 UTC | 1 464 |
| Test | décembre | 2021-12-01 00:00 à 2021-12-31 22:00 UTC | 680 |

Les comptes 6 460 / 1 464 / 680 résultent donc de la chaîne de préparation ci-dessus et de l'absence d'heures après le resampling, non d'un padding ou d'une imputation horaire.

## 3. Protocole de simulation réellement employé

### 3.1 Forme continue et paramètres

Pour tout modèle, les états sont les températures de noeuds. Le notebook construit :

~~~text
xdot = A x + b_out Tout + b_q Q
A = -diag(1 / C) K
b_out = diag(1 / C) k_out
~~~

K est le laplacien des conductances des résistances internes et des résistances vers l'extérieur. Pour chaque modèle, les paramètres optimisés sont :

~~~text
log(R0 ... R[nR-1]), log(C0 ... C[nC-1]), log(alpha)
~~~

R, C et alpha sont obtenus par exponentiation. Le gain alpha agit dans b_q ; la série Q transmise au simulateur est Qhvac_W_A.

### 3.2 Discrétisation et maintien des entrées

La cellule 55 calcule la discrétisation exacte par exponentielle d'une matrice augmentée :

~~~text
M = [ A      b_out  b_q ]
    [ 0 ...    0     0   ]
    [ 0 ...    0     0   ]

Md = expm(M × dt)
Ad = Md[états, états]
Bd_out = Md[états, colonne Tout]
Bd_q = Md[états, colonne Q]
~~~

dt vaut 3600 s. La récurrence utilise Tout[k] et Q[k] pour produire x[k+1]. Cette construction correspond à un maintien d'ordre zéro des deux entrées pendant l'intervalle [k, k+1).

### 3.3 Etat initial et mode de prédiction

Pour toute simulation :

~~~text
x[0, :] = Tin0
Tin_estime = x[:, 0]
~~~

Tin0 vaut la première mesure Tin de la période simulée. Tous les noeuds, air et masses, reçoivent cette même valeur initiale.

La simulation est en boucle ouverte : après l'initialisation, la récurrence utilise les états prédits, jamais Tin mesurée au pas suivant. Ce n'est pas une prédiction à un pas.

Le run d'entraînement, la validation et le test sont trois simulations en boucle ouverte distinctes : validation et test sont réinitialisés à leur première Tin mesurée. Le tracé annuel est une quatrième simulation en boucle ouverte distincte, réinitialisée à la première Tin de df_h et utilisant les paramètres entraînés.

### 3.4 Identification et métriques

Pour chaque modèle :

1. La perte entraînement est la moyenne de (Tin_estime - Tin_mesuree)^2 sur tout le train.
2. L'optimiseur est scipy.optimize.minimize avec method = L-BFGS-B, sans options de tolérance, de nombre maximal d'itérations ou de multi-start explicites.
3. Initialisation : tous les R à 0.2, tous les C à 1e7, alpha à 1e-4, en log-espace.
4. Bornes : log(R) dans [-10, 5], log(C) dans [8, 25], log(alpha) dans [-20, 2].
5. Le nombre de paramètres k vaut nR + nC + 1 ; les états initiaux ne sont pas comptés.
6. Validation et test emploient les paramètres du fit train sans réoptimisation.

Les métriques sont :

~~~text
RMSE = sqrt(mean(erreur²))
MAE = mean(abs(erreur))
RSS = sum(erreur²)
AIC = n ln(RSS / n) + 2k
BIC = n ln(RSS / n) + k ln(n)
~~~

La règle utilisateur validée pour la future non-régression est : BIC affiché à une décimale, valeur brute journalisée.

## 4. Banque des 19 topologies

Convention de ce document : air désigne le noeud 0 mesuré par Tin ; M1, M2, etc. désignent les masses de l'enveloppe ; Ext est la frontière Tout, donc pas un état et pas une capacité. Chaque capacité C_i est portée par le noeud i du notebook. Pour les 19 modèles, Q est injectée sur air et Tin est mesurée sur air.

### 4.1 Les dix ladders

| Modèle | Noeuds d'état | Résistances explicites | Capacités |
|---|---|---|---|
| LADDER_1R1C | air | R0 : air–Ext | C0 : air |
| LADDER_2R2C | air, M1 | R0 : air–M1 ; R1 : M1–Ext | C0 : air ; C1 : M1 |
| LADDER_3R3C | air, M1, M2 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–Ext | C0 : air ; C1 : M1 ; C2 : M2 |
| LADDER_4R4C | air, M1, M2, M3 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 |
| LADDER_5R5C | air, M1, M2, M3, M4 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–M4 ; R4 : M4–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 ; C4 : M4 |
| LADDER_6R6C | air, M1, M2, M3, M4, M5 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–M4 ; R4 : M4–M5 ; R5 : M5–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 ; C4 : M4 ; C5 : M5 |
| LADDER_7R7C | air, M1, M2, M3, M4, M5, M6 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–M4 ; R4 : M4–M5 ; R5 : M5–M6 ; R6 : M6–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 ; C4 : M4 ; C5 : M5 ; C6 : M6 |
| LADDER_8R8C | air, M1, M2, M3, M4, M5, M6, M7 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–M4 ; R4 : M4–M5 ; R5 : M5–M6 ; R6 : M6–M7 ; R7 : M7–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 ; C4 : M4 ; C5 : M5 ; C6 : M6 ; C7 : M7 |
| LADDER_9R9C | air, M1, M2, M3, M4, M5, M6, M7, M8 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–M4 ; R4 : M4–M5 ; R5 : M5–M6 ; R6 : M6–M7 ; R7 : M7–M8 ; R8 : M8–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 ; C4 : M4 ; C5 : M5 ; C6 : M6 ; C7 : M7 ; C8 : M8 |
| LADDER_10R10C | air, M1, M2, M3, M4, M5, M6, M7, M8, M9 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–M4 ; R4 : M4–M5 ; R5 : M5–M6 ; R6 : M6–M7 ; R7 : M7–M8 ; R8 : M8–M9 ; R9 : M9–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 ; C4 : M4 ; C5 : M5 ; C6 : M6 ; C7 : M7 ; C8 : M8 ; C9 : M9 |

Pour les dix lignes ci-dessus : injection Q sur air, mesure Tin sur air et condition initiale de tous les noeuds à Tin0.

### 4.2 Les neuf STD

| Modèle | Noeuds d'état | Résistances explicites | Capacités | Injection / mesure |
|---|---|---|---|---|
| STD_1R1C | air | R0 : air–Ext | C0 : air | Q : air ; Tin : air |
| STD_2R1C_parallel_losses | air | R0 : air–Ext ; R1 : air–Ext, en parallèle | C0 : air | Q : air ; Tin : air |
| STD_2R2C_air_mass | air, M1 | R0 : air–M1 ; R1 : M1–Ext | C0 : air ; C1 : M1 | Q : air ; Tin : air |
| STD_3R2C_air_shunt | air, M1 | R0 : air–M1 ; R1 : M1–Ext ; R2 : air–Ext | C0 : air ; C1 : M1 | Q : air ; Tin : air |
| STD_3R3C_two_masses_series | air, M1, M2 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–Ext | C0 : air ; C1 : M1 ; C2 : M2 | Q : air ; Tin : air |
| STD_4R3C_two_masses_plus_air_shunt | air, M1, M2 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–Ext ; R3 : air–Ext | C0 : air ; C1 : M1 ; C2 : M2 | Q : air ; Tin : air |
| STD_5R3C_air_shunt_mid_shunt | air, M1, M2 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–Ext ; R3 : air–Ext ; R4 : M1–Ext | C0 : air ; C1 : M1 ; C2 : M2 | Q : air ; Tin : air |
| STD_6R4C_three_masses_plus_shunts | air, M1, M2, M3 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–Ext ; R4 : air–Ext ; R5 : M1–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 | Q : air ; Tin : air |
| STD_7R5C_four_masses_plus_shunts | air, M1, M2, M3, M4 | R0 : air–M1 ; R1 : M1–M2 ; R2 : M2–M3 ; R3 : M3–M4 ; R4 : M4–Ext ; R5 : air–Ext ; R6 : M2–Ext | C0 : air ; C1 : M1 ; C2 : M2 ; C3 : M3 ; C4 : M4 | Q : air ; Tin : air |

### 4.3 Correspondance explicite avec la figure STD 4R3C

La figure de l'article est orientée Ext–R1–Tm1–R2–Tm2–R3–Tair, avec un shunt R4 entre Ext et Tair. Le code est orienté air–R0–M1–R1–M2–R2–Ext, avec R3 entre air et Ext.

La correspondance de graphe est :

| Indice notebook | Libellé figure |
|---|---|
| air, C0 | Tair, C_air |
| M1, C1 | Tm2, C2 |
| M2, C2 | Tm1, C1 |
| R0 | R3 |
| R1 | R2 |
| R2 | R1 |
| R3 | R4, shunt air–extérieur |

Le graphe est donc isomorphe à la figure, mais les valeurs de capacité identifiées et leur interprétation physique restent une divergence documentée séparément.

## 5. Sortie de non-régression enregistrée par la cellule 55

Les valeurs suivantes sont des sorties déjà présentes dans le notebook ; elles ne résultent pas d'une nouvelle exécution. Les valeurs BIC brutes doivent être journalisées ultérieurement ; l'affichage de référence est à une décimale.

| Modèle | k | RMSE validation brute | BIC validation brut | RMSE test brute | res.success |
|---|---:|---:|---:|---:|---|
| LADDER_1R1C | 3 | 5.006645 | 4738.189891 | 0.849438 | True |
| LADDER_2R2C | 5 | 5.006811 | 4752.864770 | 0.849500 | False |
| LADDER_3R3C | 7 | 5.006419 | 4767.213098 | 0.849068 | True |
| LADDER_4R4C | 9 | 5.006899 | 4782.071618 | 0.849477 | True |
| LADDER_5R5C | 11 | 5.006922 | 4796.663186 | 0.849496 | True |
| LADDER_6R6C | 13 | 5.006929 | 4811.245026 | 0.849502 | True |
| LADDER_7R7C | 15 | 5.006941 | 4825.829766 | 0.849512 | True |
| LADDER_8R8C | 17 | 5.006925 | 4840.398288 | 0.849498 | True |
| LADDER_9R9C | 19 | 5.006949 | 4854.990524 | 0.849521 | True |
| LADDER_10R10C | 21 | 5.006735 | 4869.442915 | 0.849339 | True |
| STD_1R1C | 3 | 5.006645 | 4738.189891 | 0.849438 | True |
| STD_2R1C_parallel_losses | 4 | 5.006727 | 4745.526725 | 0.849499 | True |
| STD_2R2C_air_mass | 5 | 5.006811 | 4752.864770 | 0.849500 | False |
| STD_3R2C_air_shunt | 6 | 4.975361 | 4741.703687 | 0.851451 | True |
| STD_3R3C_two_masses_series | 7 | 5.006419 | 4767.213098 | 0.849068 | True |
| STD_4R3C_two_masses_plus_air_shunt | 8 | 4.682382 | 4578.578337 | 0.857599 | True |
| STD_5R3C_air_shunt_mid_shunt | 9 | 5.006278 | 4781.708599 | 0.874338 | True |
| STD_6R4C_three_masses_plus_shunts | 11 | 5.022779 | 4805.921252 | 0.902459 | True |
| STD_7R5C_four_masses_plus_shunts | 13 | 5.007632 | 4811.656407 | 0.850929 | True |

Pour STD_4R3C, le notebook affiche RMSE validation 4.682 °C, BIC 4578.6 à une décimale et RMSE test 0.858 °C. Ces affichages correspondent à l'article et à la présentation.

## 6. Inventaire des plans, sans exploitation géométrique

Six plans ont été fournis, tous vectoriels, à une page et au format A3. Aucune surface, orientation, pièce ou connectivité n'a été extraite.

| Fichier / niveau | Format et échelle | Lisibilité / caractéristiques constatées |
|---|---|---|
| Edificio PLEIADES (planta baja).pdf | A3 paysage, 1:250 | bonne ; 20 calques PDF, 123 annotations AutoCAD SHX |
| Edificio PLEIADES (planta 1ª).pdf | A3 paysage, 1:250 | bonne ; 19 calques PDF, 88 annotations SHX |
| Edificio PLEIADES (planta 2ª).pdf | A3 paysage, 1:250 | bonne ; 20 calques PDF, 60 annotations SHX |
| Edificio PLEIADES (planta 3ª).pdf | A3 paysage, 1:250 | bonne ; 19 calques PDF, 45 annotations SHX |
| Edificio PLEIADES (planta 4ª).pdf | A3 avec rotation PDF 90°, affichage paysage, 1:250 | moyenne ; vectoriel, sans calque ou annotation PDF détectable, texte souvent en contours |
| Edificio PLEIADES (planta 5ª).pdf | A3 avec rotation PDF 90°, affichage paysage, 1:250 | moyenne ; vectoriel très sobre, sans calque ou annotation PDF détectable |

Les niveaux baja à 3ª proviennent d'AutoCAD 2020 (2022) ; les niveaux 4ª et 5ª de PDFCreator/Ghostscript (2017 et 2015). L'extraction géométrique est explicitement hors périmètre jusqu'à validation de la reproduction.

## 7. Hors périmètre de cette étape

- Aucune réimplémentation n'a été écrite.
- Aucun notebook n'a été exécuté ni modifié.
- Aucun choix correctif n'a été appliqué aux divergences.
- Aucun plan n'a été utilisé pour contraindre les réseaux RC.

