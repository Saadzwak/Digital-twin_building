# Auto-critique hostile — M10 chat contraint

## Exécution vérifiée

Le contexte M10 est lié au même `run_source` que M9. Le smoke a exécuté : une question RMSE autorisée, une question mur nord refusée et une demande hors périmètre refusée. Une demande nommant STD_4R3C alors que LADDER_1R1C est retenu est également refusée, sans transfert de métrique.

## Critique adversariale et corrections

1. **Affirmation fragile :** une réponse fluide ne garantit pas une preuve. **Correction :** le chat ne sert que des `IntervalEstimate` provenant des cartes M9 scellées ; sinon il refuse.
2. **Chiffre sans incertitude :** aucune réponse substantielle ne peut contenir un nombre hors carte d’intervalle. **Correction :** le type `AnswerCard` interdit les estimates sur les refus et exige une source de run sur les réponses.
3. **Hypothèse enterrée :** le chat dépend de l’identité du modèle retenu, pas de toutes les structures de la banque. **Correction :** une structure explicitement nommée différente est refusée et orientée vers la dispersion M4.
4. **Spécificité jeu de données :** le chat ne connaît que le contexte M4/M5/M9 de ce run PLEIAData. **Correction :** les demandes causales, par paroi, vitrage, économie, prix et hors périmètre sont refusées explicitement.
5. **Exécution :** la réponse autorisée, les refus et le contrôle du contexte ont été exécutés dans les tests et le smoke. **Correction :** le chat se bloque si le hash/run_source M4-M9-M10 ne concorde plus.
