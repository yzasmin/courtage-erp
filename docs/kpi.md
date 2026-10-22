Quatre indicateurs de pilotage d'un courtier délégataire, chacun défini avec sa formule, sa période, son numérateur, son dénominateur et le piège à éviter. Chaque valeur citée a été mesurée par une requête SQL de `sql/kpi/` sur les marts dbt, puis retrouvée à l'identique par Power BI.

# Indicateurs de pilotage

## Conventions communes

| Convention | Valeur | Raison |
| --- | --- | --- |
| Date d'arrêt de l'historique | 30/09/2026, dernier jour de `dim_date` | l'historique simulé s'arrête là, 2026 ne compte donc que 9 mois |
| Première période exploitable | l'année 2024 | le quittancement ne commence qu'en octobre 2023 (premier appel du 01/10/2023) : avant 2024, une cotisation acquise n'existe que pour trois mois, et le ratio n'a pas de dénominateur. En 2023, le ratio mesuré est d'environ 272 % pour cette seule raison |
| Montants | hors taxe, en euros | la taxe est reversée à l'État, elle n'est ni une prime du cabinet ni une charge de la compagnie |
| Unité de portefeuille | le contrat individuel ou le bulletin d'affiliation d'un salarié à une police collective | c'est l'unité de gestion du modèle (`docs/modele-donnees.md`) |
| Un contrat suspendu | reste au portefeuille, sans cotisation annualisée | la garantie est interrompue, pas le lien contractuel, et le contrat peut être remis en vigueur |
| Un devis | n'est jamais au portefeuille | il n'engage personne : 343 devis ne sont jamais devenus des contrats |
| Mois, pas jour | les indicateurs se lisent au mois, au trimestre ou à l'année | les cotisations acquises sont réparties par mois, les clichés du portefeuille sont pris en fin de mois |

Le modèle en étoile qui porte ces indicateurs est décrit dans `docs/powerbi-maquette.md` (tables) et dans `dbt/models/marts/`. Les requêtes de contrôle sont dans `sql/kpi/`, lancées par `make preuve-kpi`, qui écrit `results/kpi_sql.json`.

## 1. Ratio sinistres sur primes

| Rubrique | Définition |
| --- | --- |
| Formule | prestations réglées de la période ÷ cotisations acquises de la même période |
| Période | année civile, ou tout trimestre ou mois ; 2024 et 2025 complètes, 2026 sur 9 mois |
| Numérateur | `fct_prestations.rembourse_euros`, statut `reglee`, rattaché à la **date de règlement**, sur les produits dont la compagnie a délégué la gestion des prestations |
| Dénominateur | `fct_cotisations_acquises.cotisation_acquise_ht_euros`, hors taxe, mêmes produits, au prorata des jours couverts dans la période |
| Lecture | 100 % signifie que chaque euro de cotisation couru a été remboursé |
| Requête de contrôle | `sql/kpi/01_ratio_sinistres_primes.sql`, pièges chiffrés dans `01b_ratio_sinistres_primes_pieges.sql` |
| Mesure DAX | `[Ratio sinistres sur primes]`, page « Sinistres sur primes » |

### Valeurs mesurées

| Période | Prestations réglées | Cotisations acquises | Ratio |
| --- | --- | --- | --- |
| 2024 | 1 388 870,50 € | 1 818 408,62 € | 76,38 % |
| 2025 | 1 774 778,50 € | 2 218 682,28 € | 79,99 % |
| 2026 (9 mois) | 1 355 414,50 € | 1 880 726,55 € | 72,07 % |

Par branche et par exercice :

| Branche | 2024 | 2025 | 2026 (9 mois) |
| --- | --- | --- | --- |
| Santé collective | 75,55 % (734 989,00 € sur 972 798,84 €) | 79,48 % (987 049,00 € sur 1 241 810,12 €) | 73,84 % |
| Santé individuelle | 77,33 % (653 881,50 € sur 845 609,78 €) | 80,64 % (787 729,50 € sur 976 872,15 €) | 69,62 % |

La prévoyance n'a pas de ratio : voir le piège 1. Les exercices complets, 2024 et 2025, tombent dans la fourchette de 70 à 85 % que vise le calibrage ; 2026 ne compte que 9 mois, dont la santé individuelle est à 69,62 %.

Source : `results/kpi_sql.json` et `results/concordance_dax_sql.csv`.

### Comment la donnée de démonstration relie les prestations aux cotisations

Le générateur calibre le montant des demandes de chaque contrat sur **sa propre cotisation** (`_calibre_sur_la_cotisation` dans `generateur/financier.py`) : le remboursement théorique des soins d'un contrat est rendu égal à une échelle de sinistralité (`ECHELLE_SINISTRALITE` dans `generateur/parametres.py`, une valeur par branche) multipliée par la cotisation qu'il a courue, hors suspension. Chaque contrat porte donc son rapport à sa cotisation, au lieu d'un facteur global. L'échelle n'est pas le ratio publié : les contrats sans aucun soin, les plafonds, les rejets et les prestations en cours en retranchent une part, et ses valeurs ont été mesurées pour que le ratio publié, branche par branche, tombe dans la fourchette d'un portefeuille santé viable.

La consommation reste dispersée, ce qui est la propriété à garder : chaque contrat tire un multiplicateur de consommation à queue lourde (55 % de petits consommateurs, 35 % de moyens, 10 % de gros). Mesuré sur 2 066 contrats en garantie toute l'année 2025 (`sql/kpi/05_dispersion_consommation.sql`) : 8,9 % n'ont aucune prestation réglée, le contrat médian consomme 45 % de sa cotisation, le troisième quartile 106 %, le neuvième décile 200 %, le centième 528 %, et les 10 % de contrats les plus consommateurs portent 39,9 % des remboursements.

Avant ce calibrage, les prestations étaient tirées par tranche d'âge et par garantie sans rapport avec la cotisation, et les soins d'un contrat étaient limités à ses quatre premières années de garantie : le ratio atteignait 177,67 % en 2024, 152,96 % en 2025 et 121,18 % sur 9 mois de 2026. Ce défaut a été corrigé le 22/10/2026 (D32 dans `docs/DECISIONS.md`) ; l'empreinte du jeu a changé en conséquence. La prévoyance reste sans prestation, puisque l'acte n'est pas délégué : le ratio publié porte sur le périmètre délégué, ce que vérifie `dim_produit.gestion_prestations_deleguee` et le test `test_le_ratio_sinistres_sur_primes_est_plausible_dans_chaque_branche`.

### Les pièges, avec leur effet mesuré

Le même numérateur, rapporté à un autre dénominateur ou lu sur un autre périmètre :

| Variante | 2024 | 2025 | 2026 (9 mois) | Pourquoi elle est fausse |
| --- | --- | --- | --- | --- |
| **Référence** : règlement, acquises, périmètre délégué | 76,38 % | 79,99 % | 72,07 % | |
| Sur cotisations **émises** au lieu d'acquises | 75,04 % | 79,17 % | 79,26 % | une cotisation émise couvre une période qui déborde sur d'autres : en 2026, 1 710 100,57 € émis contre 1 880 726,55 € acquis, soit un écart de 9,1 % qui se retourne d'une année sur l'autre, et le ratio gagne sept points sans que rien n'ait changé |
| Prestations en **date de soins** | 78,59 % | 79,92 % | 67,11 % | les soins récents ne sont pas tous réglés : l'écart atteint cinq points sur 2026 |
| Tous produits, **prévoyance comprise** | 54,25 % | 57,35 % | 54,27 % | la prévoyance n'a aucune prestation chez le cabinet, ses cotisations diluent le ratio de 18 à 23 points |
| Sur cotisations **TTC** émises | 66,25 % | 69,89 % | 69,97 % | la taxe n'est pas une prime : le ratio paraît dix points meilleur qu'il n'est en 2024 et 2025 |

1. **Périmètre de délégation.** Les produits de prévoyance (compagnie qui n'a pas délégué les prestations) ont des cotisations dans le quittancement du cabinet et aucune prestation. Un ratio calculé sur eux est un artefact. Le périmètre est porté par `dim_produit.gestion_prestations_deleguee`, lu dans les conventions de délégation, jamais écrit en dur.
2. **Acquises contre émises.** Le dénominateur est la part de risque courue dans la période, pas ce qui a été appelé. La répartition au prorata des jours est testée : pour tout appel dont la période est écoulée, la somme des parts égale le montant appelé au centime près (`assert_cotisations_acquises_egales_aux_emises`).
3. **Date de règlement ou date de soins.** Le ratio de référence est « en date de règlement », celui que voit un délégataire qui règle les prestations. Le ratio « en date de soins » (survenance) est plus juste en théorie, mais il sous-estime la fin de l'historique faute de prestations encore déclarées, et le cabinet ne voit pas les prestations qui ne lui ont pas encore été déclarées. La mesure de contrôle `[Contrôle ratio en date de soins]` permet de les comparer.
4. **Annualisation.** Ce ratio n'est pas annualisé : numérateur et dénominateur couvrent la même période, la durée s'élimine. Annualiser le seul numérateur serait une erreur. En revanche, comparer 9 mois de 2026 à une année pleine suppose une saisonnalité nulle, ce que rien ne prouve : à lire avec prudence.

## 2. Taux de résiliation

| Rubrique | Définition |
| --- | --- |
| Formule | résiliations de la cohorte de la période ÷ contrats au portefeuille en début de période |
| Période | année civile ; sur une période plus courte, utiliser le taux annualisé |
| Numérateur | résiliations qui **prennent effet** dans la période (`fct_mouvements_portefeuille`, type `resiliation`), sur des contrats dont la date d'effet est **antérieure au premier jour** de la période |
| Dénominateur | contrats au portefeuille la **veille** du premier jour de la période : cliché de fin du mois précédent de `fct_portefeuille_mensuel`, suspendus compris |
| Taux annualisé | taux × 365 ÷ nombre de jours de la période, par proportionnalité linéaire |
| Requête de contrôle | `sql/kpi/02_taux_resiliation.sql`, pièges dans `02b_taux_resiliation_pieges.sql` |
| Mesure DAX | `[Taux de résiliation]` et `[Taux de résiliation annualisé]`, page « Résiliations » |

### Valeurs mesurées

| Période | Résiliations de la cohorte | Portefeuille en début de période | Taux | Taux annualisé |
| --- | --- | --- | --- | --- |
| 2024 | 286 | 2 605 | 10,98 % | 10,95 % (366 jours) |
| 2025 | 379 | 3 249 | 11,67 % | 11,67 % |
| 2026 (9 mois) | 321 | 3 704 | 8,67 % | 11,59 % (273 jours) |

Par branche en 2025 : santé collective 14,52 %, prévoyance 9,97 %, santé individuelle 9,73 %.

Source : `results/kpi_sql.json` et `results/concordance_dax_sql.csv`.

### Les pièges, avec leur effet mesuré

| Variante | 2024 | 2025 | 2026 (9 mois) | Pourquoi elle est fausse |
| --- | --- | --- | --- | --- |
| **Référence** : cohorte sur effectif de début | 10,98 % | 11,67 % | 8,67 % | |
| Rapporté à l'effectif de **fin** de période | 8,80 % | 10,23 % | 8,18 % | l'effectif de fin contient des contrats entrés pendant la période, qui n'ont pas pu être résiliés dans le même exercice : le taux est sous-estimé de 2 points en 2024 |
| Rapporté à l'effectif **moyen** | 9,77 % | 10,90 % | 8,41 % | mélange un stock de début et un stock de fin, sans définition métier |
| **Non annualisé** sur 9 mois | | | 8,67 % | comparé à 10,98 % et 11,67 % il suggère une amélioration de trois points qui n'existe pas : annualisé, 2026 vaut 11,59 % |

1. **Portefeuille au début, pas à la fin.** Le dénominateur est un cliché daté. Le modèle le lit la veille du premier jour : une résiliation datée du 1er janvier tombe dans l'année qui commence, et le contrat est bien dans l'effectif du 31 décembre. Cette convention est vérifiée par une identité stock et flux testée dans dbt (`assert_flux_egal_variation_du_stock`) : l'effectif de fin de mois est celui du mois précédent, plus les affaires nouvelles, moins les résiliations.
2. **Cohorte.** Une résiliation d'un contrat né dans la même période n'a pas son contrat au dénominateur : elle est écartée du numérateur. Sur ce jeu, aucune résiliation de ce type n'a été mesurée en 2024, 2025 ni 2026 (colonne `nees_et_resiliees_dans_la_periode` de `02b_taux_resiliation_pieges.sql` : 0 sur les trois périodes) : la règle ne change rien aujourd'hui, mais elle protège le calcul d'une période plus courte ou d'un autre jeu.
3. **Annualisation.** L'approximation linéaire suppose un taux faible et une période d'au moins un trimestre. Elle est identique en SQL et en DAX, ce qui ne prouve que l'identité des deux calculs, pas la validité de l'approximation.
4. **Motifs.** Le taux compte tous les motifs. Le décès, le transfert de portefeuille et la résiliation par la compagnie n'ont pas la même nature qu'un départ de l'adhérent : la page Power BI ventile par motif, et le choix d'exclure certains motifs est un arbitrage de gestion que la définition ne tranche pas.

## 3. Production par apporteur

| Rubrique | Définition |
| --- | --- |
| Formule | nombre d'affaires nouvelles, et cotisation annualisée de ces affaires, par apporteur |
| Période | année civile, trimestre ou mois |
| Numérateur (nombre) | contrats mis en vigueur dans la période : avenant de mise en vigueur, hors remise en vigueur après suspension, hors devis |
| Numérateur (cotisation) | cotisation mensuelle hors taxe **au jour de la mise en vigueur** × 12 |
| Dénominateur | sans objet pour le volume ; pour la part de production, le total de tous les apporteurs sur la même période |
| Rattachement | l'apporteur en vigueur le jour de la mise en vigueur, lu dans l'avenant, pas l'apporteur courant du contrat |
| Requête de contrôle | `sql/kpi/03_production_par_apporteur.sql`, pièges dans `03b_production_par_apporteur_pieges.sql` |
| Mesure DAX | `[Affaires nouvelles]`, `[Cotisation annualisée des affaires nouvelles]`, `[Part de la production]`, page « Production par apporteur » |

### Valeurs mesurées

Totaux : 930 affaires et 730 192,08 € annualisés en 2024, 834 et 655 274,04 € en 2025, 543 et 420 264,24 € sur 9 mois de 2026.

Détail 2025, classé par cotisation annualisée :

| Apporteur | Affaires nouvelles | Cotisation annualisée |
| --- | --- | --- |
| Littoral Conseil Entreprises (AP06) | 94 | 74 565,84 € |
| Mireille Fabre, agent général (AP05) | 92 | 71 826,60 € |
| Production directe, guichet en ligne (AP10) | 93 | 71 497,68 € |
| Comparassur en ligne (AP04) | 83 | 67 097,16 € |
| Occitane Patrimoine (AP02) | 85 | 65 784,60 € |
| Réseau Garrigue Assurances (AP03) | 84 | 64 998,72 € |
| Cabinet Vidal Courtage (AP01) | 83 | 64 087,68 € |
| Cévennes Prévoyance Conseil (AP07) | 73 | 59 788,92 € |
| Production directe, équipe commerciale (AP09) | 76 | 59 558,28 € |
| Devis-Santé.fr (AP08) | 71 | 56 068,56 € |

Source : `results/kpi_sql.json`. Le jeu compte dix apporteurs, tous actifs.

### Les pièges, avec leur effet mesuré (année 2025)

1. **Apporteur courant ou apporteur de la mise en vigueur.** Sur les 834 affaires de 2025, 26 contrats ont depuis changé d'apporteur. Les rattacher à l'apporteur courant créditerait à l'un la production d'un autre, et réécrirait un classement déjà communiqué.
2. **Cotisation courante ou cotisation d'origine.** La cotisation annualisée serait de 692 435,64 € avec la cotisation courante des mêmes contrats, contre 655 274,04 € à la mise en vigueur : 37 161,60 € de revalorisations ultérieures attribuées à une production passée.
3. **Remise en vigueur.** Compter les remises en vigueur donnerait 900 « affaires » au lieu de 834 : 66 sont des contrats suspendus remis en vigueur, pas des affaires nouvelles.
4. **Annualisée n'est pas appelée.** Ni la cotisation appelée dans la période (qui dépend du fractionnement et du jour d'effet), ni la cotisation acquise : c'est un rythme annuel de régime, pas un flux comptable.

## 4. Portefeuille par branche

| Rubrique | Définition |
| --- | --- |
| Formule | contrats au portefeuille et cotisation annualisée, à une date, par branche |
| Période | une **date** : le dernier jour d'un mois (fin de la période lue) |
| Numérateur | contrats en cours et suspendus au cliché (`fct_portefeuille_mensuel`), devis et résiliés exclus |
| Cotisation annualisée | cotisation mensuelle hors taxe × 12 des seuls contrats **en cours** au cliché : un contrat suspendu ne donne lieu à aucun appel |
| Dénominateur | sans objet (stock) ; la part par branche est le rapport à l'ensemble au même cliché |
| Requête de contrôle | `sql/kpi/04_portefeuille_par_branche.sql`, pièges dans `04b_portefeuille_par_branche_pieges.sql` |
| Mesure DAX | `[Contrats au portefeuille]`, `[dont suspendus]`, `[Cotisation annualisée du portefeuille]`, page « Portefeuille par branche » |

### Valeurs mesurées

| Date | Branche | Contrats | Dont suspendus | Cotisation annualisée |
| --- | --- | --- | --- | --- |
| 31/12/2023 | Prévoyance | 754 | 0 | 678 740,52 € |
| 31/12/2023 | Santé collective | 922 | 0 | 757 466,52 € |
| 31/12/2023 | Santé individuelle | 929 | 0 | 761 296,80 € |
| 31/12/2024 | Prévoyance | 893 | 0 | 809 265,96 € |
| 31/12/2024 | Santé collective | 1 267 | 0 | 1 053 239,28 € |
| 31/12/2024 | Santé individuelle | 1 089 | 0 | 904 688,04 € |
| 31/12/2025 | Prévoyance | 993 | 0 | 918 298,68 € |
| 31/12/2025 | Santé collective | 1 528 | 0 | 1 297 353,12 € |
| 31/12/2025 | Santé individuelle | 1 183 | 0 | 1 012 997,64 € |
| 30/09/2026 | Prévoyance | 1 024 | 10 | 962 832,12 € |
| 30/09/2026 | Santé collective | 1 683 | 13 | 1 457 565,96 € |
| 30/09/2026 | Santé individuelle | 1 219 | 13 | 1 058 438,28 € |

Au 30/09/2026 : 3 926 contrats, dont 36 suspendus, et 3 478 836,36 € de cotisation annualisée.

Source : `results/kpi_sql.json`. Le total de 3 926 est recoupé par un second chemin : le nombre de contrats dont le statut courant est « en cours » ou « suspendu » (3 926 également, `04b_portefeuille_par_branche_pieges.sql`), et un test dbt compare les deux contrat par contrat (`assert_portefeuille_final_egal_statut_courant`).

### Les pièges, avec leur effet mesuré (au 30/09/2026)

1. **Un stock ne s'additionne pas.** La somme des douze clichés de 2025 est de 41 542 « contrats », pour un portefeuille de 3 704 à la fin de l'année. Le modèle impose la lecture à une date : la mesure prend le cliché de la fin de la période sélectionnée.
2. **Les devis ne sont pas des contrats.** Compter tout ce qui n'est pas résilié donne 4 269 contrats, soit 343 devis de trop.
3. **Cotisation d'un suspendu.** Inclure les suspendus dans la cotisation annualisée donne 3 511 851,36 €, soit 33 015,00 € de trop, de la cotisation qui n'est pas appelée.
4. **Statut courant et cotisation courante.** Pour une lecture à la **date d'arrêt**, le statut courant et le cliché coïncident (3 926 et 3 478 836,36 € des deux côtés). Pour toute autre date, seul le cliché est exact : le statut courant a changé depuis.

## Concordance entre Power BI et SQL

Les mesures DAX ont été évaluées par le moteur local de Power BI Desktop, puis comparées à des requêtes SQL écrites indépendamment sur les marts (`scripts/concordance_kpi.py`). Résultat : **302 comparaisons, 21 mesures, 46 contextes de filtre, aucun écart au-delà de l'arrondi des flottants, écart relatif maximal 2,9e-14** (`results/concordance_dax_sql.json`, détail ligne à ligne dans `results/concordance_dax_sql.csv`).

| Mesure | Contexte | DAX | SQL | Écart relatif |
| --- | --- | --- | --- | --- |
| Ratio sinistres sur primes | 2025 | 0,79992458449685 | 0,7999245844968472 | 3,5e-15 |
| Ratio sinistres sur primes | 2025, santé collective | 0,79484695840369 | 0,7948469584036898 | 2,8e-16 |
| Ratio sinistres sur primes | 2026 | 0,720686640814817 | 0,7206866408148135 | 4,9e-15 |
| Taux de résiliation | 2025 | 0,116651277316097 | 0,11665127731609726 | 2,3e-15 |
| Taux de résiliation | 2025, santé collective | 0,145224940805051 | 0,1452249408050513 | 2,1e-15 |
| Taux de résiliation annualisé | 2026 | 0,115868203071227 | 0,11586820307122683 | 1,4e-15 |
| Contrôle ratio sur cotisations émises | 2025 | 0,791687948444878 | 0,7916879484448776 | 5,6e-16 |
| Cotisation annualisée des affaires nouvelles | 2025 | 655 274,04 | 655 274,04 | 0 |
| Cotisation annualisée des affaires nouvelles | 2025, AP06 | 74 565,84 | 74 565,84 | 0 |
| Affaires nouvelles | 2025, AP06 | 94 | 94 | 0 |
| Part de la production | 2025, AP06 | 0,113793368038813 | 0,11379336803881318 | 1,6e-15 |
| Contrats au portefeuille | 2026 | 3 926 | 3 926 | 0 |
| Cotisation annualisée du portefeuille | 2026 | 3 478 836,36 | 3 478 836,36 | 0 |
| Cotisation annualisée du portefeuille | 2026, prévoyance | 962 832,12 | 962 832,12 | 0 |

Ce que cette concordance prouve : le modèle sémantique Power BI calcule ce que la définition SQL calcule, sur 21 mesures et 46 contextes. Ce qu'elle ne prouve pas : que la définition est la bonne. C'est le rôle des sections précédentes, et du jugement de gestion.

Les 21 mesures comparées incluent les mesures de contrôle (variantes « fausses » des pièges), pour que le tableau de bord puisse montrer lui-même l'effet d'un mauvais choix de définition.

## Comment rejouer

```bash
make marts-pilotage       # dbt build : modèle en étoile et tests (PostgreSQL du compose)
make preuve-kpi           # requêtes de sql/kpi/, écrit results/kpi_sql.json
make exporter-powerbi     # marts vers powerbi/donnees/*.csv
make pbip DONNEES="C:\chemin\vers\courtage-erp\powerbi\donnees"   # projet Power BI, chemin local
# ouvrir powerbi/Pilotage-Courtage.pbip dans Power BI Desktop, puis, depuis PowerShell :
.\scripts\executer_dax.ps1 -Actualiser
make concordance-kpi      # DAX contre SQL
```
