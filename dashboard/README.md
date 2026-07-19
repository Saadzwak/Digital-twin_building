# Produit de diagnostic thermique

Lancer depuis la racine du projet :

```powershell
python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 61730 --server.headless true --browser.gatherUsageStats false
```

Puis ouvrir http://127.0.0.1:61730

## Parcours

1. **Accueil** : déposer un plan (PDF) et des mesures (CSV : horodatage, T
   intérieure, T extérieure, consommation HVAC), ou cliquer sur « Essayer avec
   le bâtiment Pleiades » (jeu public déjà présent).
2. **Analyse en direct** : le calcul s'exécute réellement — inventaire des
   plans, préparation des données, banc des 19 structures (3 départs chacune)
   avec un graphique complexité/écart construit point par point, sélection,
   dérive annuelle, scénarios. Aucune progression simulée.
3. **Onboarding** : 4 questions (répondre « inconnu » est valable).
4. **Tableau de bord** : résumé (4 indicateurs), dérive datée plein écran,
   ce que le modèle a identifié (langage métier), scénarios d'intervention
   chiffrés en énergie, détail méthodologique replié (rigueur complète), chat.

## Garanties maintenues

- Aucun chiffre sans incertitude ; verdict route B affiché ; aucune
  attribution par paroi individuelle ; géométrie bloquée tant que non validée
  humainement ; chaque valeur traçable jusqu'à son run source.
- Le niveau de déperdition absolu est signalé « non robuste entre calages »
  quand les calages équivalents divergent (cas de la référence Pleiades).

Le protocole du pipeline produit est dans
[`docs/produit_demo_protocol.md`](../docs/produit_demo_protocol.md) ; il est
distinct du protocole gelé de reproduction M4, qui reste inchangé.
