# Auto-critique hostile — M6 inventaire des plans

## Exécution vérifiée

Six PDFs de plans ont été inventoriés et rendus en aperçus : niveaux basse à 5, une page chacun, 1191 × 842 pt. Les niveaux basse à 3 portent une échelle détectée 1:250 ; les niveaux 4 et 5 ont une rotation de 90° et aucune échelle textuelle détectée. Le statut reste `HUMAN_VALIDATION_REQUIRED`.

## Critique adversariale et corrections

1. **Affirmation fragile :** une échelle textuelle détectée n’établit pas que le périmètre thermique est le bon. **Correction :** aucune surface, volume ou ratio vitrage n’est calculé ni injecté au modèle.
2. **Chiffre sans incertitude :** dimensions de page, nombre de tracés et échelle détectée sont des métadonnées d’inventaire, pas des mesures du bâtiment. **Correction :** les métriques géométriques restent nulles jusqu’à validation humaine.
3. **Hypothèse enterrée :** l’orientation nord, les hauteurs et la frontière du bloc A ne peuvent pas être inférées de manière fiable. **Correction :** elles sont explicitement demandées dans le contrat M8.
4. **Spécificité document :** l’extraction dépend du texte/vectoriel de ces six PDFs ; les niveaux 4–5 sont particulièrement peu lisibles automatiquement (zéro caractère extrait). **Correction :** la lisibilité est signalée par l’inventaire et les aperçus, sans surinterprétation.
5. **Exécution :** inventaire et création d’aperçus ont été exécutés, et les tests confirment six pages uniques. **Correction :** une tentative d’inspection visuelle directe via le visualiseur a été bloquée par la sandbox Windows ; cela ne déverrouille aucun calcul et la validation humaine demeure obligatoire.
