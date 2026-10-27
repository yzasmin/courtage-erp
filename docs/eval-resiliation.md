Évaluation de la prédiction de résiliation (module 5). Chiffres tirés de `results/ml_resiliation.json`, produit par `make entrainer-ml` le 27/10/2026.

# Prédiction de résiliation : évaluation

## À lire d'abord

**Les données sont synthétiques.** Les causes de résiliation ont été écrites dans le générateur, puis
retrouvées par le modèle. L'intérêt n'est donc pas la performance, qui ne dit rien d'un portefeuille réel,
mais la démarche : aucune fuite d'information, une validation dans le temps, un modèle simple préféré
quand le modèle complexe ne fait pas mieux, et des explications lisibles par un gestionnaire.

## La question posée

Au 1er janvier, jour de l'échéance et de la revalorisation, quels contrats en cours vont être résiliés dans
les douze mois ? C'est le moment où le cabinet peut encore appeler l'adhérent, revoir la formule ou
négocier avec la compagnie.

## Ce qui garantit l'absence de fuite

- Les variables sont construites dans dbt (`dbt/models/ml/ml_variables_resiliation.sql`), à chaque 1er du
  mois, à partir des seuls avenants d'effet antérieur ou égal à la date d'observation.
- Le test `assert_ml_aucune_information_posterieure` le revérifie à chaque construction, y compris dans le
  graphe Airflow mensuel : un test en échec arrête le scoring.
- La cible n'est renseignée que si ses douze mois sont entièrement observés. C'est pourquoi le test porte
  sur 2025 et non sur 2026 : la fenêtre du 1er janvier 2026 dépasse la fin de l'historique, et les
  résiliations à l'échéance du 1er janvier 2027 y manqueraient (décision D34).
- La sinistralité n'est pas une variable : l'historique des prestations commence le 01/10/2023, elle
  vaudrait zéro aux dates d'apprentissage par absence de données (décision D35).

## Découpage

| Jeu | Date d'observation | Contrats au portefeuille | Résiliés dans les douze mois |
| --- | --- | --- | --- |
| Apprentissage | 01/01/2023 et 01/01/2024 | 4 546 | 568 |
| Test | 01/01/2025 | 3 216 | 413 (12,8 %) |

Hyperparamètres de LightGBM fixés avant de regarder le test, jamais retouchés ensuite.

## Résultats sur l'année de test

| Mesure | Régression logistique (déployée) | LightGBM | Plafond : la formule du générateur |
| --- | --- | --- | --- |
| ROC-AUC | 0,645 | 0,645 | 0,662 |
| PR-AUC (hasard : taux de base) | 0,218 | 0,204 | 0,214 |
| Score de Brier (plus bas est meilleur) | 0,1088 | 0,1113 | 0,1075 |
| Taux de résiliation dans le premier décile | 28,6 % | 25,5 % | 28,9 % |
| Lift du premier décile | 2,22 | 1,98 | 2,25 |

**Lecture.** Le plafond est la probabilité que le générateur a réellement utilisée, recalculée sur les
mêmes contrats. Aucun modèle ne peut faire mieux en moyenne : chaque résiliation est un tirage au sort, et
une ROC-AUC autour de 0,65 est ce que permet ce tirage. La régression logistique en est très proche. Sa
PR-AUC dépasse même légèrement celle du plafond, ce qui relève de l'aléa sur 413 résiliations et des
résiliations pour impayé, produites par un autre mécanisme du générateur.

**Pourquoi la régression logistique est déployée** (décision D37). LightGBM était prévu comme le modèle
plus performant. Il ne l'est sur aucune mesure, et il est moins bien calibré : il annonce
38,0 % de risque dans le décile le plus risqué, où l'on observe 25,5 %. Les causes du
générateur se combinent par des facteurs multiplicatifs, exactement la forme d'une régression logistique.
Sur des données réelles, l'écart pourrait changer de sens : LightGBM est donc recalculé à chaque
apprentissage, et c'est la mesure qui décidera.

## Calibration du modèle déployé, par décile de risque

| Décile | Probabilité prédite | Taux observé |
| --- | --- | --- |
| 1 | 4,0 % | 5,3 % |
| 2 | 6,2 % | 6,8 % |
| 3 | 7,8 % | 9,0 % |
| 4 | 9,5 % | 10,9 % |
| 5 | 11,2 % | 10,6 % |
| 6 | 13,2 % | 11,2 % |
| 7 | 15,8 % | 12,2 % |
| 8 | 19,0 % | 17,4 % |
| 9 | 23,1 % | 16,5 % |
| 10 | 31,9 % | 28,6 % |

Le modèle surestime le risque : 14,2 % en moyenne pour 12,8 % observés, et l'écart se concentre dans le
haut de l'échelle, jusqu'à 6,6 points au neuvième décile. L'ordre des déciles, lui, est respecté à une
inversion près (neuvième et huitième). Pour classer les contrats à appeler, c'est sans conséquence ; pour annoncer un nombre de
résiliations attendu, il faudrait le recalibrer.

## Ce que le modèle a appris, confronté aux causes injectées

Contribution moyenne (valeur SHAP, en log-cote) de la variable concernée, dans le groupe exposé à la cause
et dans le reste du portefeuille, sur l'année de test.

| Cause écrite dans le générateur | Effet attendu | Contribution, exposés | Contribution, autres | Taux observé, exposés | Taux observé, autres |
| --- | --- | --- | --- | --- | --- |
| revalorisation de 6 % ou plus (1 506 contrats) | hausse | 0,65 | -0,15 | 17,5 % | 8,8 % |
| ancienneté de moins de 18 mois (1 303 contrats) | hausse | 0,28 | -0,38 | 17,4 % | 9,7 % |
| 60 ans ou plus (726 contrats) | baisse | -0,21 | 0,06 | 7,6 % | 14,4 % |
| apporteurs AP04 et AP08 (601 contrats) | hausse | 0,50 | -0,11 | 17,0 % | 11,9 % |

Les quatre causes sont retrouvées, toutes dans le bon sens. Les quatre variables les plus influentes du
modèle sont exactement ces quatre causes ; la cotisation et le nombre de suspensions, qui ne jouent aucun
rôle dans la formule, ont une contribution quasi nulle.

| Variable | Contribution moyenne absolue |
| --- | --- |
| revalorisation au dernier 1er janvier | 0,435 |
| ancienneté | 0,346 |
| apporteur | 0,223 |
| âge | 0,124 |
| produit | 0,066 |
| branche | 0,043 |
| changements de formule | 0,026 |
| affiliation collective | 0,025 |
| suspensions passées | 0,001 |
| cotisation mensuelle | 0,000 |
| suspendu à la date | 0,000 |

## Explication locale, sur la fiche adhérent

Chaque mois, le graphe `courtage_scoring_resiliation` écrit pour chaque contrat sa probabilité, son décile
et les trois variables qui poussent son risque **à la hausse**, rédigées comme un gestionnaire les dirait :
« Revalorisation de 6,2 % au dernier 1er janvier », « Apporté par AP04 », « Ancienneté de 10 mois ». Un
facteur qui fait baisser le risque n'est jamais affiché à côté d'un score élevé (décision D39). Pour un
modèle linéaire, ces valeurs SHAP sont exactes : coefficient multiplié par l'écart à la moyenne
d'apprentissage.

## Rejouer

```bash
make variables-ml   # variables et test de non-fuite (dbt, PostgreSQL)
make entrainer-ml   # apprentissage, mesures, results/ml_resiliation.json
make scorer-ml      # scores du dernier mois dans la table score_resiliation
```
