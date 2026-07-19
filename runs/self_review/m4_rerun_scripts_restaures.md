# Auto-critique — restauration des scripts et ré-exécution M4 single-start

Date d’exécution : 2026-07-19.

## Ce qui a été exécuté

Les six scripts (`run_m1_reference`, `run_m3_determinism`, `run_m4_reproduction`,
`run_m6_inventory`, `run_m8_onboarding`, `run_m10_chat_check`) ont été restaurés
depuis leurs sauvegardes `.pre_src_path_fix` avec la seule insertion de `src`
dans `sys.path`, conformément au patch prévu (`tmp/patches/fix_script_bootstrap.patch`).
Chacun a été exécuté sur les données réelles :

- M1 : 8604 lignes, splits 6460/1464/680, CSV bit à bit identique (hash inchangé).
- M3 : déterminisme bitwise confirmé.
- M4 : 19 fits reproduits ; identiques à l’historique à 12 décimales, pas bit à bit.
- M6/M8/M10 : artefacts régénérés conformes.

## Critique adversariale

1. **Quelle affirmation ne survivrait pas à un examen ?**
   « La ré-exécution M4 reproduit l’historique » sans qualificatif : elle le
   reproduit aux 12 décimales journalisées mais diffère de quelques ulp
   (~3e-13 °C). **Correction :** écart documenté en H-M4-05, non masqué.
2. **Quel chiffre est affiché sans son incertitude ?**
   Les valeurs single-start restent étiquetées non validées et hors produit ;
   aucun chiffre utilisateur ne provient de ce run.
3. **Quelle hypothèse est enterrée dans le code ?**
   La tolérance de régénération 1e-9 du test. **Correction :** nommée en
   constante avec renvoi à H-M4-05.
4. **Qu’est-ce qui marche uniquement sur ce jeu de données ?**
   La reconstruction bit à bit du CSV historique est impossible sans les octets
   d’origine ; l’histoire scellée vit dans `single_start_verdict.json`, intact
   depuis le run initial et désormais épinglé par SHA-256 dans le test.
5. **Où ai-je écrit « ça marche » sans l’avoir exécuté ?**
   Nulle part : chaque script restauré a été exécuté, et la suite complète a
   été relancée après la modification du test.
