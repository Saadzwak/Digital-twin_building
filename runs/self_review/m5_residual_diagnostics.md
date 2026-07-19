# Auto-critique hostile — M5 diagnostic du résidu

## Exécution vérifiée

`runs/m5/diagnostic.json` a été régénéré depuis le fit M4 scellé `m4-multistart-a9ba009bce9e3659` (LADDER_1R1C, départ 29). Convention unique : `Tin_measured - Tin_estimated`. Les CSV train/validation/test et leurs versions recalibrées ont été écrits, et les tests réels M5 ont passé.

## Critique adversariale et corrections

1. **Affirmation fragile :** une rupture locale n’est pas la cause d’un changement de régime. **Correction :** chaque rupture est libellée comme signal diagnostique, avec échelle MAD locale et sans attribution causale.
2. **Chiffre sans incertitude :** RMSE et moyenne sont accompagnés de bootstrap par blocs à 95 %. Médiane, MAD et autocorrélation restent des statistiques de diagnostic internes, non affichées comme cartes de produit. **Correction :** aucune carte dashboard n’expose ces statistiques seules.
3. **Hypothèse enterrée :** les intervalles sont calculés sur le plus long segment sans lacune, pas sur tous les points du split. **Correction :** `metric_segment_policy` et `contiguous_segment_n` sont désormais écrits pour chaque split. Cela explique notamment que le RMSE test M5 (`0.9687 °C`, segment 448) diffère du RMSE M4 sur le split test entier (`0.8495 °C`, 680 points) ; ce ne sont pas la même population de calcul.
4. **Spécificité jeu de données :** seuil 24 h, MAD ×3, tertiles Tout et bootstrap 24 h sont calibrés comme diagnostics sur cette cadence et ces lacunes PLEIAData. **Correction :** la méthode et la non-transférabilité implicite sont journalisées ; la recalibration est train-only et n’est pas vendue comme paramètre physique.
5. **Exécution :** les diagnostics ont été exécutés sur les données réelles et testés ; aucune phrase de conformité ne repose sur un mock. **Correction :** le test de matérialisation relance le flux réel depuis l’artefact M4 validé.
