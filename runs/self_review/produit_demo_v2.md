# Auto-critique hostile — produit démonstrable (P1–P7)

Date d'exécution : 2026-07-19. Artefacts : `runs/demo/latest/`, protocole dans
`docs/produit_demo_protocol.md`, 72 tests exécutés.

## Ce qui a été exécuté

Pipeline en direct réel (plans → données → banc 19×3 → sélection → jumeau →
dérive → scénarios), 127 s au premier parcours navigateur complet ; smoke
AppTest (accueil, onboarding, sections, chat) ; 21 nouveaux tests dont
équivalence simulateur (<1e-7 °C), identité d'inversion de consigne (1e-4 W),
rupture synthétique datée exactement, rupture réelle épinglée (2021-10-03 /
2021-11-15).

## Critique adversariale et corrections

1. **Quelle affirmation ne survivrait pas à un examen ?**
   « Niveau de déperdition : 63 W/°C » présenté comme un fait : des calages
   équivalents en validation impliquent jusqu'à ×97 d'écart. **Correction
   exécutée :** drapeau `robust_between_calibrations` calculé au moteur,
   affiché en surface (« valeur non robuste entre calages »), repris par le
   chat, testé. Ce qui est robuste — le signe et l'ordre de grandeur des
   scénarios — est affiché avec sa fourchette inter-calages.

2. **Quel chiffre est affiché sans son incertitude ?**
   Les métriques du résumé portent leurs fourchettes en aide contextuelle et
   dans les sections ; la date de rupture porte sa bande (±) et sa règle de
   persistance. Les comptes d'audit (heures lues, calages effectués) sont des
   comptages exacts, étiquetés comme tels.

3. **Quelle hypothèse est enterrée dans le code sans être visible ?**
   Trois choix produits pouvaient l'être : jumeau = paramétrisation publiée
   (et non la sélection du banc), règle d'admissibilité 2× médiane, seuils de
   rupture 3σ/14 jours. **Correction :** les trois sont écrits dans
   `docs/produit_demo_protocol.md`, affichés dans l'interface (étape 4,
   détail méthodologique) et couverts par des tests.

4. **Qu'est-ce qui marche uniquement sur ce jeu de données précis ?**
   Le jumeau « article » n'existe que pour PLEIAData ; un CSV déposé reçoit la
   sélection du banc avec des indicateurs possiblement « non lisibles », et le
   dit. La détection de rupture suppose une période de calage d'au moins
   ~30 jours. Le chrono (~2–3 min) dépend de la machine.

5. **Où ai-je écrit « ça marche » sans l'avoir exécuté ?**
   Le dépôt de fichiers (upload CSV/PDF) est implémenté et couvert par le
   parseur testé indirectement, mais le parcours navigateur complet n'a été
   exécuté qu'avec le bouton démo — l'upload réel depuis le navigateur n'a
   pas été rejoué de bout en bout. C'est déclaré dans la remise comme
   fonctionnel non rejoué en navigateur, pas comme vérifié.

## Fait sensible à ne pas maquiller

Le banc en direct écarte LADDER_5R5C (bassin dégénéré MSE 43) et le déclare à
l'écran. Le jumeau d'exploitation n'est PAS la sortie du banc : c'est la
paramétrisation publiée de l'article, choisie et affichée comme telle parce
que la re-identification automatique converge vers des solutions sans lecture
physique. Le verdict B scellé reste la référence méthodologique.
