# M4 — diagnostic comparatif après échec de reproduction

## Verdict exécuté

Les 19 labels ont été exécutés sur les données réelles M1, avec les bornes,
l’initialisation, le split et l’appel L-BFGS-B gelés. Le verdict est **échec de
reproduction**.

| Critère non négociable | Attendu | Observé | Verdict |
|---|---:|---:|---|
| Labels exécutés | 19 | 19 | conforme |
| Autres structures dans RMSE validation [4.98, 5.02] | 18 / 18 | 15 / 18 | échec |
| STD 4R3C RMSE validation | 4.682382 | 5.007034573212 | échec |
| STD 4R3C BIC validation | 4578.578337 | 4774.862180096648 | échec |
| STD 4R3C RMSE test | 0.857599 | 0.849648062482 | échec |

Les résultats bruts ligne par ligne, les doublons conservés et les statuts sont
dans `reproduction_19_models.csv`. Les valeurs ne sont pas arrondies dans ce
fichier.

## Faits qui excluent déjà certaines explications

1. M1 produit bien 8 604 lignes et les splits 6 460 / 1 464 / 680.
2. L’oracle matriciel 4R3C, la ZOH et le signe des résidus sont testés.
3. En injectant les paramètres imprimés par le notebook, sans optimisation,
   la même réimplémentation donne sur nos données : RMSE val `4.682382239969`,
   BIC val `4578.578335283145`, RMSE test `0.857599213887`. Le test dédié a
   été exécuté et passe à la tolérance liée à la précision imprimée des
   paramètres.
4. Le fit local 4R3C converge formellement (`success=True`, 71 itérations,
   1 332 évaluations) vers le bassin générique de RMSE validation 5.007, non
   vers le bassin de l’article. Il ne s’agit donc pas d’un statut ignoré.

## Comparaison de code, bloc par bloc

La matrice détaillée est dans `docs/m4_protocol_line_by_line.md`. Résumé :

| Composant cellule 55 | Équivalent exécuté | Conclusion actuelle |
|---|---|---|
| Split Jan–Sep / Oct–Nov / Dec | M1 + `split_reference_months` | conforme aux tailles et bornes |
| Graphe 4R3C | M2 oracle | conforme ; paramètres notebook reproduisent val/test |
| `expm` augmentée / ZOH / état initial | M2 tests + oracle paramètres | conforme |
| `x0`, bornes, `minimize(..., L-BFGS-B)` | M3 exact, sans options | même spécification déclarative |
| Trajectoire numérique de l’optimiseur | SciPy local 1.17.1 | différente de la sortie notebook |
| Agrégation Tin | sommes/comptes streaming | formule identique, ordre de somme possiblement différent à l’ulp |

## Hypothèses classées, non résolues

1. **Runtime non épinglé (priorité haute).** Le notebook ne donne pas ses
   versions SciPy/NumPy/BLAS. L-BFGS-B et son gradient numérique peuvent suivre
   un bassin différent sur ce problème non convexe.
2. **Jeu train historique non bit-identique (priorité moyenne).** Les métriques
   validation/test obtenues avec les paramètres imprimés sont quasi exactes,
   mais le train du notebook n’est pas sauvegardé. Le streaming M1 change
   potentiellement l’ordre d’addition ; le zip peut aussi différer du snapshot
   Colab.
3. **Paramètres imprimés tronqués (priorité basse).** Cela explique le résidu
   d’environ 1e-6 de l’oracle, pas l’écart de 0.325 °C du fit local.

Un fait notable est que les paramètres notebook imprimés donnent, sur notre
train, une MSE de `3.4495346040701054`, alors que le bassin local 4R3C donne
`3.258575540610`. Avec la précision imprimée disponible, le bassin notebook
semble donc moins bon pour la perte train locale mais meilleur en validation.
Ce constat est diagnostique, pas une correction ni une interprétation causale.

## Actions expressément non faites

- aucune borne, initialisation, tolérance, nombre d’itérations ou multi-start
  n’a été modifié ;
- aucun paramètre n’a été repris pour forcer les chiffres ;
- le fit 4R3C n’a pas été relancé après échec seulement pour extraire son
  vecteur ;
- aucune revendication produit ou diagnostic de résidu réel n’est fondé sur ce
  run invalide.

Les modules suivants sont implémentés avec un verrou explicite sur
`runs/m4/verdict.json` : ils peuvent être testés sur des fixtures, mais refusent
de présenter une identité thermique, un classement ou une recommandation issue
d’un M4 non validé.
