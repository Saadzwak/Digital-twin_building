# Auto-critique hostile — M8 onboarding

## Exécution vérifiée

Le contrat M8 contient quatre questions (maximum autorisé : cinq) : frontière thermique, nord, hauteurs et vitrage. Toutes sont actuellement `not_asked`; toute réponse inconnue désactive la capacité dépendante sans valeur par défaut.

## Critique adversariale et corrections

1. **Affirmation fragile :** quatre réponses ne rendent pas la géométrie automatiquement correcte. **Correction :** l’acceptation humaine M6 reste une étape distincte.
2. **Chiffre sans incertitude :** aucune donnée numérique n’est demandée ou affichée comme mesurée ; les réponses servent à autoriser ou non des calculs ultérieurs.
3. **Hypothèse enterrée :** ne pas demander de résistance surfacique est intentionnel. **Correction :** le contrat indique que M7 conserve un unique r'' libre, plutôt que de figer un paramètre utilisateur.
4. **Spécificité bâtiment :** les questions relient les PDFs au bloc A du jeu PLEIAData ; elles ne sont pas une enquête générique de performance énergétique. **Correction :** chaque question documente ce qu’elle débloque.
5. **Exécution :** le contrat et ses tests (quatre questions, états inconnus, absence de r'') ont été exécutés.
