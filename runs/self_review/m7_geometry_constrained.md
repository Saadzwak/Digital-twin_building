# Auto-critique hostile — M7 structures contraintes

## Exécution vérifiée

Le statut écrit est `HUMAN_GEOMETRY_VALIDATION_REQUIRED`, avec `fit_executed=false`. La structure prête lorsque la géométrie est acceptée impose `R_i = r'' / A_i` et garde un seul paramètre libre partagé `r''`.

## Critique adversariale et corrections

1. **Affirmation fragile :** connaître des surfaces ne permet pas d’identifier une perte indépendante par façade. **Correction :** la limite d’identifiabilité est écrite dans l’état M7 et dans l’interface.
2. **Chiffre sans incertitude :** aucun chiffre géométrique ou paramètre M7 réel n’est affiché, car aucun fit n’a été exécuté.
3. **Hypothèse enterrée :** les branches reçoivent le même forçage extérieur ; seule leur conductance agrégée est identifiable. **Correction :** cette hypothèse est exposée dans `status.json`.
4. **Spécificité données :** la réduction à un r'' commun suppose une géométrie et une frontière thermique approuvées pour ce bâtiment. **Correction :** le garde humain empêche toute exécution actuelle.
5. **Exécution :** les tests de contrainte exacte et de garde M4/M6 sont exécutés ; aucun « fit géométrique » n’est prétendu.
