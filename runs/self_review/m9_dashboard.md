# Auto-critique hostile — M9 dashboard

## Exécution vérifiée

Le payload M9 a été matérialisé depuis les artefacts M4/M5 au même `run_source` scellé : `m4-multistart-a9ba009bce9e3659`. Il contient 19 lignes de dispersion, le bandeau B obligatoire, les cartes d’identité, pertes effectives, dérive et scénarios. Les tests de contrat et de rendu BIC ont passé ; le smoke AppTest a rendu les huit sections.

## Critique adversariale et corrections

1. **Affirmation fragile :** la structure au meilleur BIC de validation parmi les départs train-sélectionnés (LADDER_1R1C) n’est pas « la vraie physique du bâtiment ». **Correction :** l’interface la nomme structure RC effective et affiche la limite d’identifiabilité.
2. **Chiffre sans incertitude :** toutes les grandeurs estimées du dashboard passent par `IntervalEstimate` (valeur, bornes, unité, période, méthode, source). Les seuls nombres sans intervalle sont des comptes d’audit exacts (départs finis / départs prévus) explicitement étiquetés comme tels. **Correction :** BIC est affiché à une décimale, la valeur brute restant journalisée.
3. **Hypothèse enterrée :** les intervalles des paramètres/scénarios sont une dispersion empirique des départs, pas des IC. **Correction :** le bandeau permanent B et la méthode de chaque carte l’explicitent.
4. **Spécificité jeu de données :** les contrefactuels utilisent les forçages du test PLEIAData et ne sont ni des économies ni des effets de travaux. **Correction :** les captions et méthodes le disent, et aucun classement n’est intitulé recommandation.
5. **Exécution :** les 8 sections, le bandeau B et les cartes sourcées ont été exécutés avec AppTest. **Correction :** le smoke échoue si une section ou le bandeau requis est absent.
