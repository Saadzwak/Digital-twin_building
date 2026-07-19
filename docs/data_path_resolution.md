# Résolution des données de référence

Le chemin effectif des octets fournis est résolu automatiquement depuis la
racine du projet. La source immuable est `Data_Nature.zip`, dont le manifeste
contient `Data_Nature/data/` (et non le chemin littéral
`Data_Nature/raw_data/` attendu par le notebook Colab).

Ordre de résolution :

1. `data/raw/Data_Nature/data/` après extraction minimale locale ;
2. `Data_Nature/data/` à la racine ;
3. `Data_Nature/raw_data/` pour compatibilité avec le notebook ;
4. à défaut, extraction exclusivement de `data-sensor.csv`, `data-cons.csv`,
   `relations-sensor.csv` et `MU62_dm.txt` depuis `Data_Nature.zip` vers 1.

Aucun fichier pré-agrégé de l’archive ne peut être sélectionné silencieusement.
Le manifeste produit par M1 journalise le chemin réellement résolu et le
SHA-256 de l’archive. Pour l’archive fournie :

```text
6296cf25af1df0f5c416d1c4e6c31c979a9967e16051cf353c73df64a8f36416
```

Sous pandas 3, l’alias historique `1H` du notebook est refusé. Le code emploie
`1h`, de sémantique identique, et signale explicitement cette adaptation d’API
dans le manifeste ; elle ne change ni la grille ni les règles d’agrégation.
