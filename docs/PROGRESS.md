État réel du projet courtage-erp : ce qui est fait, ce qui reste, et comment reprendre. Mis à jour le 27/10/2026 (module 5 livré).

# Avancement

## État en une ligne

**Module 1, cœur ERP : fait et prouvé sur les deux moteurs, avec des prestations reliées aux cotisations depuis le 22/10. Module 2, flux financiers : fait et
mesuré. Module 3, pilotage : fait, projet Power BI ouvert et mesures contrôlées contre le SQL.** Module 6,
documentation et présentation : fait. **Module 5, prédiction de résiliation : fait le 27/10.** **Module 4a, agent de pré-remplissage : fait le 27/10.** Module 4b **non réalisé**. La capture du graphe
Airflow existe (`docs/captures/08-graphe-airflow.jpg`) mais date d'avant l'ajout de la tâche `alerter`.

| Étape | État |
| --- | --- |
| 0, connaître la cible | vérifié, 19/10/2026, la note de cadrage métier, conservée hors du dépôt (`docs/CIBLE.md`, exclu par `.gitignore`) |
| 1, cœur ERP | **fait**, preuves dans `results/` |
| 2, flux financiers Airflow et dbt | **fait**, preuves dans `results/`, une capture d'écran en attente |
| 3, pilotage Power BI | **fait**, preuves dans `results/`, captures dans `docs/captures/08` à `13` |
| 4a, agent de pré-remplissage | **fait** le 27/10/2026 : `docs/eval-extraction.md`, `results/ia_evaluation.json`, 30 réponses enregistrées dans `data/ia/reponses/` |
| 4b, RAG conditions générales | **non réalisé** |
| 5, prédiction de résiliation | **fait** le 27/10/2026 : `docs/eval-resiliation.md`, `results/ml_resiliation.json`, `results/ml_scoring.json` |
| 6, documentation finale et page de présentation | **fait** : README, `docs/DEMO.md`, `docs/POUR-LA-DIRECTION.md`, fiche et teaser du portfolio, fiche d'entretien. Le rendu de la vidéo et le build du site restent à lancer |

## Module 1 : ce qui est livré

### Modèle de données

23 tables, décrites et justifiées une par une dans `docs/modele-donnees.md`, avec un diagramme Mermaid.

- Référentiel : branche, compagnie, apporteur, produit, garantie, formule, formule_garantie, taux_taxe,
  taux_commission, taux_retrocession.
- Délégation de gestion : convention_delegation, convention_produit, acte_delegue.
- Portefeuille : entreprise_souscriptrice, adherent, contrat, avenant.
- Flux : appel_cotisation, encaissement, prestation, commission, retrocession, bordereau.

Les tables `commission`, `retrocession` et `bordereau` existent mais sont **vides** : elles sont
remplies par la chaîne du module 2, qui calcule les commissions. C'est un choix, pas un oubli : les
générer ici reviendrait à écrire deux fois la même règle de calcul.

### Cycle de vie et délégation

Quatre statuts, `devis`, `en_cours`, `suspendu`, `resilie`. Un devis ne se résilie pas, un contrat
résilié est terminal, un contrat suspendu reste au portefeuille. Le motif de résiliation est obligatoire,
et la règle est portée par l'API **et** par une contrainte en base.

La délégation de gestion est vérifiée avant toute écriture qui engage la compagnie. Le jeu de
démonstration pose trois périmètres différents, pour que le refus soit visible dans les données :

| Compagnie | Portée | Ce qu'elle ne délègue pas |
| --- | --- | --- |
| Océane Assurances | totale | rien, hors sinistres |
| Pyrène Mutuelle | partielle | l'encaissement : elle prélève elle-même |
| Littoral Prévoyance | partielle | les prestations et les sinistres |

### API et interface

API FastAPI documentée par OpenAPI, dont l'endpoint `GET /api/v1/contrats/{numero}/etat` qui reconstitue
l'état d'un contrat à n'importe quelle date et indique de quel avenant provient la valeur retournée.

Interface Jinja2 et HTMX, sans chaîne Node : accueil, liste et fiche adhérent, portefeuille, fiche
contrat, saisie d'un contrat, écran des anomalies de rapprochement, écran de validation des dossiers
pré-remplis, réseau et délégations. Captures dans `docs/captures/`.

## Chiffres mesurés

Toutes ces valeurs viennent d'une exécution enregistrée dans `results/`. Aucune n'est estimée.

### Jeu de démonstration, graine 20261019, historique arrêté au 30/09/2026

| Entité | Lignes | Source |
| --- | --- | --- |
| Entreprises souscriptrices | 40 | `results/generation.json` |
| Adhérents | 5 382 | idem |
| Contrats | 5 737 | idem |
| Avenants | 28 816 | idem |
| Polices collectives | 40 | idem |
| Appels de cotisation | 51 324, dont les appels groupés des polices | idem |
| Lignes d'appel groupé | 23 855 | idem |
| Encaissements | 37 154 | idem |
| Prestations | 49 970 | idem |
| **Total des lignes empreintées** | **178 658** | `results/reproductibilite_sqlite.json` |

Durée de génération : 14,30 s sur SQLite (`results/generation.json`, champ `duree_generation_s`).
La mesure sur PostgreSQL en conteneur n'a pas été reprise après la régénération : elle n'est donc plus
citée ici plutôt que d'être recopiée périmée.

### Preuves du module 1

| Preuve | Résultat | Fichier |
| --- | --- | --- |
| Migrations qui montent et redescendent, SQLite | conforme, 8 révisions, 33 tables, aucun résidu (rejoué le 27/10) | `results/migrations_sqlite.json` |
| Migrations qui montent et redescendent, PostgreSQL | conforme, 8 révisions, 33 tables, aucun résidu (rejoué le 27/10, base temporaire) | `results/migrations_postgresql.json` |
| Génération reproductible, SQLite | deux exécutions, empreinte identique | `results/reproductibilite_sqlite.json` |
| Génération reproductible, PostgreSQL | deux exécutions, empreinte identique | `results/reproductibilite_postgresql.json` |
| **Même empreinte sur les deux moteurs** | `ff90a24da37721ff684efa5f0bbfee43730c3ef7c1d356910803ccfcf9546ff5` | les deux fichiers ci-dessus |
| Suite de tests, base temporaire | 255 passés, 13 sautés | `results/pytest.txt` |
| Suite de tests, base de démonstration | 250 passés, 1 sauté | `results/pytest_base_demonstration.txt` |
| Suite de tests, PostgreSQL | produite par l'intégration continue, voir l'artefact du travail `le meme code sur la base de production` | `results/pytest_postgresql.txt` |
| Cohérence métier des données, deux moteurs | 18 contrôles, tous conformes | `results/coherence_metier.json` |
| Les tests détectent les défauts qu'ils couvrent | 9 mutations, toutes détectées | `results/mutation.json` |
| La base refuse les écritures interdites, en SQL direct | 5 écritures sur 5 refusées, sur les deux moteurs | `results/contraintes_sqlite.json`, `results/contraintes_postgresql.json` |
| Pile Docker démarrée sur le poste | service d'initialisation code 0, application saine | `results/docker_compose.txt` |

Les tests « sautés » sont ceux qui n'ont pas d'objet sur la base concernée : les tests de signaux
réalistes se déclarent sautés tant qu'aucun portefeuille n'est généré, et le garde-fou du dossier
temporaire ne s'applique pas quand la base est fournie explicitement.

### Empreinte mémoire de la pile Docker

Mesurée avec `docker stats`, machine virtuelle Docker de 4 031 537 152 octets, soit environ 3,75 Go
(`results/docker_compose.txt`) :

| Conteneur | Mémoire utilisée | Limite déclarée |
| --- | --- | --- |
| Application ERP | 66,21 Mio | 512 Mio |
| PostgreSQL | 101,5 Mio | 512 Mio |

Environ 168 Mio au total. L'enveloppe restante est confortable pour les services Airflow du module 2,
qui sont dimensionnés pour un exécuteur local sans Celery ni Redis.

### Pourquoi l'empreinte a changé

L'empreinte du jeu de démonstration est passée de `fea8ef82…` à `f22fe41f…`, puis à `3311d29f…`, puis à
`ff90a24d…`, et le nombre de lignes de 168 901 à 178 814, puis à 178 086, puis à 178 658. Les deux
changements du 21/10 sont expliqués plus bas, dans la section « Reprise du 21/10/2026 », le dernier dans la
section « Recalibrage de la sinistralité du 22/10/2026 ». C'est normal et voulu : **les données ont changé parce que le modèle métier a été
corrigé.** Une empreinte qui serait restée identique après ces corrections aurait signifié qu'elles
n'avaient rien produit.

Ce qui explique l'écart, dans l'ordre d'importance :

| Correction | Effet sur les données |
| --- | --- |
| Santé collective modélisée en police | 40 polices et 23 855 lignes d'appel apparaissent ; les 2 382 appels individuels des salariés deviennent des appels groupés, d'où la baisse de 70 629 à 51 324 appels |
| Portefeuille antérieur à la fenêtre de données | les contrats démarrent dès 2019, d'où 28 816 avenants au lieu de 19 490, et un portefeuille déjà constitué au 1er janvier 2024 |
| Prestations hors suspension et plafond annuel cumulé | le nombre de prestations change, et une demande entièrement plafonnée devient un rejet motivé |
| Convention de délégation arrivée à échéance | le quittancement du produit concerné s'arrête au 30 juin 2026 |
| Résiliation infra-annuelle interdite avant douze mois | les motifs de sortie se redistribuent |

La reproductibilité, elle, est intacte : deux exécutions de même graine donnent la même empreinte, et
SQLite et PostgreSQL produisent un jeu identique octet pour octet.

## Critères d'acceptation du module 1

| Critère | État | Preuve |
| --- | --- | --- |
| Migrations qui montent et descendent proprement | conforme | `results/migrations_sqlite.json`, `results/migrations_postgresql.json` |
| Génération reproductible, même graine, mêmes données | conforme | empreinte SHA-256 identique sur deux exécutions et sur deux moteurs |
| Diagramme entité-association commenté | conforme | `docs/modele-donnees.md` |
| Tests sur les transitions de statut | conforme | `tests/test_cycle_vie.py` |
| Tests sur la reconstitution à date | conforme | `tests/test_avenants.py` |

Exigences venues en cours de module, également tenues : délégation de gestion au modèle avec refus testé
(`tests/test_delegation.py`), et aucun paramètre métier écrit en dur dans le code, tous en base avec des
dates de validité (`docs/HYPOTHESES.md`).

## Défauts trouvés et corrigés pendant le module

Tous ont été trouvés par les tests ou par le passage sur PostgreSQL, et aucun n'est resté ouvert.

| Défaut | Comment il a été trouvé | Leçon |
| --- | --- | --- |
| Les données d'un test fuyaient dans le suivant | neuf tests en erreur en cascade | `docs/lessons/p8-sqlite-savepoint-pysqlite.md` |
| Trois formats de réponse d'erreur selon la route | un test d'API sur le corps de la réponse | corrigé dans `api/app.py` |
| Une dérogation de rétrocession pouvait être moins avantageuse que l'accord cadre auquel elle dérogeait | la suite rejouée avec la graine de démonstration | corrigé dans `generateur/referentiel.py` |
| Le script de preuve se figeait sur PostgreSQL | exécution contre la base du compose | `docs/lessons/p8-postgres-connexion-inspection-bloque-ddl.md` |
| Deux tests utilisaient `strftime`, propre à SQLite | suite rejouée sur PostgreSQL | corrigé dans `tests/test_generation.py` |

## Reste à faire

### Module 2 : ce qui reste

- **Capture d'écran du graphe Airflow : faite**, `docs/captures/08-graphe-airflow.jpg`, mais antérieure à
  l'ajout de la tâche `alerter` (la capture montre treize tâches, le graphe en compte quatorze). À reprendre
  si la pile Docker est relancée.
- **Vérification par un sous-agent à contexte vierge : faite le 27/10/2026** pour l'ensemble des modules,
  voir « Vérification indépendante du 27/10/2026 ».

### Modules suivants

Les étapes 4a et 5 ne dépendent plus que du module 2 et ne partagent aucun fichier : elles peuvent
être menées en parallèle. L'étape 3 est faite (section « Module 3 » plus bas).

## Module 2 : ce qui est livré

### La chaîne

Neuf étapes, de la réception des bordereaux au bordereau de rétrocession de l'apporteur, documentées une
par une dans `docs/flux-financiers.md`. Chaque étape est une commande `courtage flux <étape>`, et le
graphe Airflow les appelle en ligne de commande plutôt que d'importer le code métier.

- **Générateur de fichiers reçus** et son manifeste de vérité terrain : bordereaux de cotisations en CSV
  et en XLSX avec ligne de total, relevés bancaires, bordereaux de prestations, anomalies injectées,
  fichiers corrigés renvoyés après rejet, et un fichier redéposé octet pour octet.
- **Huit contrôles bloquants et deux non bloquants**, tous exécutés avant la première écriture.
- **Rapprochement** par référence puis par montant et date, fenêtre paramétrable, quatre statuts.
- **Commissions et rétrocessions** au taux valide à la date d'échéance, assiette paramétrée en base.
- **Bordereaux mensuels** par compagnie et par apporteur, en base et en CSV.
- **Projet dbt** en trois couches, avec ses tests de qualité, sa documentation et son lineage.

### Preuves, toutes dans `results/`

| Preuve | Fichier | Résultat mesuré |
| --- | --- | --- |
| Sortie de `dbt build` | `dbt_build.txt` | 199 réussites, 4 avertissements, 0 erreur (le modèle en étoile du module 3 compris) |
| Journal d'exécution par lot | `flux_journal_lots.json` | un lot par fichier, avec empreinte, verdict et motif |
| Rapport de détection | `flux_rapport_detection.json` | rappel et précision par code et par sévérité |
| Rejet intégral d'un lot | `flux_rejet_integral.json` | 9 lots rejetés, 0 ligne écrite |
| Idempotence | `flux_idempotence.json` | 27 fichiers redéposés, empreinte d'état identique |
| Rapprochement | `flux_rapprochement.json` | par statut et par méthode |
| Commissions | `flux_commissions.json` | créées, mises à jour, inchangées, et appels écartés avec leur motif |
| Bordereaux | `flux_bordereaux.json` | 9 bordereaux de commissions, 24 de rétrocessions |
| Exécution du graphe Airflow | `airflow_execution.md` | états des tâches et artefacts laissés sur le disque |

Les captures sont dans `docs/captures/` : `06-lineage-dbt-complet.jpg` et
`07-lineage-dbt-commissions.jpg`.

### Défauts trouvés en mesurant, pas en relisant

| Défaut | Comment il a été trouvé |
| --- | --- |
| Le contrôle du total comparait la ligne de total à une somme incomplète quand une ligne était illisible | un lot à une anomalie injectée en signalait deux |
| Le contrôle du plafond cumulait l'année entière, prestations postérieures comprises | précision de 0,10 sur ce code |
| L'alerte « proche du plafond » se répétait à chaque prestation d'un adhérent déjà au-delà du seuil | 745 signalements pour 71 anomalies injectées |
| L'anomalie de période injectée ne tombait pas toujours hors garantie | le contrôle ne trouvait rien, et le manifeste annonçait une anomalie inexistante |
| Les comptes rendus des tâches atterrissaient dans l'environnement virtuel du conteneur | exécution du graphe |
| Deux conteneurs partageant un volume avec deux identifiants d'utilisateur différents | archivage en échec sur une permission refusée |
| Le sélecteur dbt retenait des tests dont les parents n'existaient pas encore | tâche de transformation en échec |
| La référence d'un lot, tirée du seul nom de fichier, entrait en collision sur un renvoi corrigé | exécution du graphe |

Les deux leçons du module sont dans `docs/lessons/`, index à jour.

### Relecture par deux agents, et ce qui en a été retenu

Deux agents à contexte vierge ont relu le code : `ecc:python-reviewer` sur la correction, et
`ecc:silent-failure-hunter` sur les échecs silencieux. Chaque remarque a été vérifiée dans le code avant
d'être retenue ou écartée.

**Retenu et corrigé, par ordre de gravité :**

| Défaut | Conséquence s'il était resté |
| --- | --- |
| Les contrôles ne reprenaient pas les contraintes de vérification de la base | une ligne contraire à un invariant faisait **planter** le chargement au lieu de rejeter le lot, et aucun lot suivant n'était traité |
| Un fichier illisible, encodage ou archive corrompue, levait une exception | même effet : la chaîne s'arrêtait au lieu de rejeter le lot |
| `convertit_montant` laissait fuir `OverflowError` et `InvalidOperation`, et acceptait `1e400`, `1_000`, `1e3` | exception technique hors du rejet, et entiers de 400 chiffres envoyés à la base |
| L'archive était nommée d'après le seul nom du fichier | un renvoi corrigé sous le même nom **écrasait la pièce d'audit** du premier envoi |
| Une ligne vide en fin de fichier masquait la ligne de total | rejet à tort d'un fichier conforme, cas courant des exports de tableur |
| Un fichier sans aucune ligne de donnée était chargé comme un succès | un relevé bancaire vide marquait le mois comme servi, et tous les appels étaient ensuite écartés sans motif lisible |
| Les commissions et rétrocessions devenues caduques n'étaient pas supprimées au recalcul | une rétrocession continuait d'être payée à un apporteur que plus rien ne justifiait |
| Un mois dont le relevé était rejeté sortait du périmètre sans un mot | aucune commission calculée, chaîne verte, personne prévenu |
| Le tri des lots se faisait par nom de fichier | sous une collation linguistique PostgreSQL, une copie pouvait passer avant son original, et c'est l'original qui aurait été rejeté |
| `--periode` n'était pas ramenée au premier du mois | calcul partiel silencieux, puis bordereau vide |
| `--fenetre-jours` acceptait une valeur négative | le rapprochement par montant et date se désactivait sans erreur |
| Les bordereaux CSV étaient écrits avant la validation en base | des documents prêts à être envoyés sans contrepartie en base |
| La sortie console n'affichait que les valeurs simples | les journaux Airflow cachaient la ventilation des écarts |
| Le générateur pouvait annoncer au manifeste une anomalie que le contrôle ne peut pas lever | faux négatif fabriqué, rappel mesuré faussé |
| Les deux preuves pouvaient conclure « conforme » sur un périmètre vide | une preuve qui ne prouve rien |

Cinq tests ont été ajoutés pour ces cas, et l'assertion de rejet est passée de « le motif attendu figure
parmi les motifs » à « le motif attendu est le seul ». Plusieurs tests auraient pu passer pour une
mauvaise raison.

**Écarté, avec la raison :**

- *Rendre « contrat inconnu » non bloquant sur un relevé bancaire.* La spécification liste ce contrôle
  comme bloquant sans distinguer le flux. L'argument du relecteur, une référence saisie à la main est
  facile à mal taper, est juste et noté comme limite, mais il demande un arbitrage métier que le projet
  ne peut pas prendre seul.
- *Ajouter une contrainte d'unicité sur `rapprochement_ligne.reference_bancaire`.* Correct sur le fond.
  Le risque est une exécution concurrente, or le graphe est en `max_active_runs=1` et l'autre chemin est
  une commande lancée à la main. Reporté plutôt qu'improvisé en fin de module.
- *Charger les taux et les périmètres de délégation en mémoire plutôt que par date.* Gain de
  performance sans effet sur la justesse, sur une chaîne qui traite onze mille lignes en deux minutes.
- *Horodater les comptes rendus JSON pour en garder l'historique.* `results/` porte le dernier état
  prouvé ; l'historique par lot est en base, dans `lot_fichier`, et c'est le journal qui fait foi.
- *Capteur de complétude du courrier attendu et bordereau rectificatif.* Fonctionnalités utiles mais
  hors du périmètre du module 2, et à décider avec le métier.
- *`_montant` écrirait `12,5` au lieu de `12,50`.* Vérifié par exécution : `centimes_vers_euros(1250)`
  rend `Decimal('12.50')`. La remarque ne tenait pas.

## Module 3 : ce qui est livré

### Le modèle en étoile

Complété, pas refait : les marts du module 2 (`dim_date`, `dim_produit`, `dim_compagnie`, `dim_apporteur`,
`fct_cotisations`, `fct_prestations`, `fct_commissions`) sont conservés. Ajoutés : `dim_branche`,
`dim_adherent` (tranche d'âge, département, sans donnée nominative), `fct_cotisations_acquises`,
`fct_mouvements_portefeuille` (affaires nouvelles et résiliations), `fct_portefeuille_mensuel` (cliché de fin de
mois), et `int_contrat_versions` (versions successives d'un contrat). `dim_date` couvre désormais le portefeuille
dès 2019, `dim_produit` porte le périmètre de délégation des prestations. Le tableau de bord est déclaré en
exposure (`tableau_de_bord_pilotage`, onze marts en parents), visible dans le lineage
(`docs/captures/13-lineage-dbt-tableau-de-bord.jpg`).

### Indicateurs, requêtes de contrôle, tableau de bord

| Livrable | Où | Preuve |
| --- | --- | --- |
| Quatre indicateurs définis, avec pièges chiffrés | `docs/kpi.md` | valeurs de `results/kpi_sql.json` |
| Une requête de contrôle par indicateur, et une requête des pièges | `sql/kpi/` (8 fichiers) | `make preuve-kpi` |
| Projet Power BI PBIP, modèle TMDL, 26 mesures commentées, 5 pages, 49 visuels | `powerbi/` | ouvert dans Power BI Desktop 2.159.883.0, captures `docs/captures/08` à `12` |
| Maquette | `docs/powerbi-maquette.md` | |
| Concordance DAX contre SQL | `docs/kpi.md`, `results/concordance_dax_sql.csv` | 302 comparaisons, 21 mesures, 46 contextes, écart relatif maximal 2,9e-14 |
| Sortie de `dbt build` | `results/dbt_build.txt` | 52 modèles, 151 tests, 3 exposures : 199 réussites, 4 avertissements, 0 erreur |

### Les quatre indicateurs mesurés

| Indicateur | Valeur | Source |
| --- | --- | --- |
| Ratio sinistres sur primes | 76,38 % en 2024, 79,99 % en 2025, 72,07 % sur 9 mois de 2026 | `results/kpi_sql.json`, `01_ratio_sinistres_primes` |
| Taux de résiliation | 10,98 % en 2024, 11,67 % en 2025, 8,67 % sur 9 mois de 2026 (11,59 % annualisé) | `02_taux_resiliation` |
| Production par apporteur | 834 affaires et 655 274,04 € annualisés en 2025, dix apporteurs | `03_production_par_apporteur` |
| Portefeuille par branche | 3 926 contrats, dont 36 suspendus, et 3 478 836,36 € annualisés au 30/09/2026 | `04_portefeuille_par_branche` |

### Intégration continue

Dernière exécution : 39720480639 sur le commit `8a81132`, réussie en 3 min 25 s. La précédente (39720045926, recalibrage D32) avait échoué sur un test dépendant de l'ordre des lignes sous PostgreSQL, corrigé depuis. Exécution 39685738522 sur le commit `97dcc4f` : réussie en 3 min 26 s (suite de 238 tests, style, 7 tests du projet Power BI). `gh run list --repo yzasmin/courtage-erp` donne l'état courant.

### Défauts trouvés pendant le module

| Défaut | Comment il a été trouvé | État |
| --- | --- | --- |
| Le recalcul SQL des commissions ignorait la règle D24, que le code applique : deux tests de sévérité erreur échouaient sur 1 184 appels | premier `dbt build` complet sur la base régénérée | **corrigé** (D31), voir `docs/lessons/p8-sql-et-application-appliquent-la-meme-regle.md` |
| Un test passait de 4 secondes à 24 minutes après la correction | commande dépassant son délai, requête encore active dans `pg_stat_activity` | **corrigé** : modèle matérialisé en table, 2 secondes |
| La base PostgreSQL du compose contenait un jeu antérieur à la reprise du 21/10 (50 126 prestations et 2 520 commissions au lieu de 49 398 et 3 704) | comptage avant le premier build | **corrigé** : base recréée et régénérée, empreinte `3311d29f…` retrouvée, identique à SQLite |
| Le ratio sinistres sur primes dépassait 100 % sur toutes les périodes (177,67 %, 152,96 %, 121,18 %) | premières valeurs mesurées | **corrigé le 22/10** : le générateur reliait mal les prestations aux cotisations ; voir D32 et la section « Recalibrage de la sinistralité » |
| Power BI Desktop installé est en 2.159.883.0, non en 2.157.1354.0 | `Get-AppxPackage` | consigné, vérification faite sur la version installée |

### Limites ouvertes

- **L'intégration continue n'exécute pas dbt** (il demande PostgreSQL et la chaîne de flux). Le défaut D24 est resté
  invisible pour cette raison. Les tests de `tests/test_pbip.py` couvrent la cohérence du projet Power BI sans Power BI.
- **Le projet Power BI versionné porte un chemin d'exemple** pour les données : à adapter après un clone
  (`make pbip DONNEES=...`). Les CSV (18 Mo) ne sont pas versionnés.
- **Les captures du tableau de bord sont celles d'un seul poste**, à une résolution (voir `docs/powerbi-maquette.md`).

### Commandes du module 3

```bash
make marts-pilotage       # dbt build : modèle en étoile et tests (PostgreSQL du compose)
make preuve-kpi           # requêtes de sql/kpi, écrit results/kpi_sql.json
make exporter-powerbi     # marts vers powerbi/donnees/*.csv
make pbip DONNEES="C:\chemin\vers\courtage-erp\powerbi\donnees"
.\scripts\executer_dax.ps1 -Actualiser   # PowerShell, projet ouvert dans Power BI Desktop
make concordance-kpi      # DAX contre SQL
```

## Module 4a : ce qui est livré

- **Documents** : `courtage ia generer`, 30 PDF fictifs qui citent de vrais adhérents et contrats du jeu,
  et leur vérité terrain ; 8 portent une anomalie volontaire.
- **Extraction** : Claude Haiku 5.5, schéma JSON strict, revalidation Pydantic, réponses enregistrées avec
  l'empreinte de la requête ; mode hors ligne par défaut.
- **Contrôles et dossiers** : table `dossier_pre_rempli` (migration 0008, appliquée sur SQLite et, depuis
  la reconstruction des images du 27/10, sur PostgreSQL), écran « Dossiers à valider », validation qui crée la prestation
  par `enregistre_prestation`, rejet motivé.
- **Mesuré le 27/10 en appel réel** puis rejoué hors ligne à l'identique : précision 96,7 % (290 champs sur
  300), 20 documents entièrement exacts, anomalies 8 sur 8, aucun document sain bloqué, 0,000272 $ et
  1 807 ms en moyenne par document, 0,0081 $ pour les 30. Les 10 erreurs portent toutes sur l'émetteur des
  demandes de remboursement (le modèle ajoute « Service prestations ») ; la vérité terrain n'a pas été
  retouchée après coup.
- **Deux règles corrigées par la mesure** : seuil de nom (D44, trouvé par les tests) et attestation pendant
  une suspension (D45, trouvé par l'évaluation).
- **Tests** : 14 dans `tests/test_ia.py`, dont un verrou de non-régression qui rejoue les 30 réponses.
- **Non fait** : module 4b. Vérification indépendante faite le 27/10, voir plus bas.

## Module 5 : ce qui est livré

- **Variables** : modèle dbt `ml_variables_resiliation` (schéma `analytique_ml`), un 1er du mois par ligne de
  janvier 2021 à septembre 2026, et deux tests : une ligne par contrat et par date, aucun avenant postérieur
  lu. `dbt build` du modèle et de ses dépendances : 65 réussites, aucun échec.
- **Apprentissage** : `courtage ml entrainer`, apprentissage sur les 1er janvier 2023 et 2024 (4 546 contrats,
  568 résiliations), test sur le 1er janvier 2025 (3 216 contrats, 413 résiliations).
- **Mesures sur 2025** : régression logistique ROC-AUC 0,645, PR-AUC 0,218, lift du premier décile 2,22 ;
  LightGBM 0,645, 0,204, 1,98 ; plafond de la formule du générateur 0,662, 0,214, 2,25. La régression
  logistique est déployée (D37). Les quatre variables les plus influentes sont les quatre causes appliquées
  par le générateur, dans le bon sens.
- **Scoring** : `courtage ml scorer`, 3 926 contrats scorés au 01/09/2026 dans la table `score_resiliation`
  (migration 0007), affichés sur la fiche adhérent avec trois facteurs. Graphe Airflow mensuel
  `courtage_scoring_resiliation` **exécuté avec succès dans Airflow le 27/10/2026**, après reconstruction de
  l'image avec l'option `ml` : 1 min 06 s au total (variables 43 s, scoring 17 s) depuis l'optimisation de la
  cible (D48).
- **Tests** : 3 tests ajoutés (`tests/test_resiliation.py`) ; suite complète 241 réussis, 13 ignorés.
- **Écart trouvé** : la sinistralité est déclarée comme cause dans les paramètres mais non appliquée par le
  générateur. Documentation corrigée, générateur inchangé (D35, `docs/HYPOTHESES.md`).
- **Vérification indépendante** : faite le 27/10, voir plus bas.

## Vérification indépendante du 27/10/2026

Un sous-agent à contexte vierge a relu la spécification, contrôlé chaque critère contre le code et des
exécutions réelles, parcouru 250 écrans (tous en HTTP 200) et joué un dirigeant d'éditeur de logiciel de
courtage. Verdict : code solide, démo pas prête. Corrections faites le jour même :

| Défaut relevé | Correction |
| --- | --- |
| Parcours `DEMO.md` impossible sur SQLite : aucun score, aucun dossier | Chemin A : `courtage ia traiter` ajouté, score montré par capture (dbt demande PostgreSQL) ; chemin B : graphe de scoring déclenché et `erp-cli ia traiter` ; commandes sans `make`, qui n'est pas installé sous Windows ; minutage porté à 150 s avec deux étapes nouvelles |
| Image de l'ERP ancienne (migration 0007 introuvable) et sans l'option `ia` | Images reconstruites, option `ia` ajoutée, migration 0008 appliquée sur PostgreSQL par `erp-init` |
| Chiffres périmés (238 tests, 6 révisions, 31 tables, 6 bordereaux de commissions) | Preuves rejouées : 255 tests, 8 révisions et 33 tables sur SQLite et PostgreSQL ; 9 bordereaux |
| Remboursement santé calculé sur les frais présentés, sans base de remboursement ni régime obligatoire | **Déclaré, pas corrigé** : le corriger changerait les 49 970 prestations générées et tous les ratios mesurés. Simplification affichée sur la fiche contrat, dans `HYPOTHESES.md` et dans les limites du README |
| Cotisation annualisée de l'accueil et du réseau comptant les suspendus | Corrigée : seuls les contrats en cours, comme le définit `kpi.md` |
| Date de règlement d'une prestation validée égale à la date des soins | Corrigée : jour de l'enregistrement par défaut, vérifiée par un test |
| Écran des dossiers : messages sans accents, dates ISO, montants à point, « adhérent inconnu » suivi de « contrat rattaché » | Corrigé ; le contrat d'un adhérent introuvable passe en alerte « rattachement non vérifiable » |

Restent à faire, hors de ces corrections : pousser le commit, mettre à jour la fiche du portfolio, préparer
en entretien les points de vocabulaire relevés (AP05 « agent général », rejet intégral d'un relevé bancaire,
moment du scoring).

## Commandes pour reprendre

Sans Docker, sur SQLite, pour développer et tester vite :

```bash
make installer
make regenerer        # redescend le schema, le remonte, regenere le jeu de demonstration
make tests            # 255 tests sur une base temporaire
make servir           # http://127.0.0.1:8000
```

Avec Docker, sur PostgreSQL, comme en production :

```bash
docker compose up -d --build     # PostgreSQL, migrations, generation, application
make etat                        # etat des conteneurs et empreinte memoire reelle
make preuve-postgres             # rejoue migrations, reproductibilite et tests sur PostgreSQL
```

Rejouer toutes les preuves du module 1 :

```bash
make preuves                     # sur SQLite
make tests-demonstration         # active les tests de signaux realistes
```

`make aide` liste toutes les commandes.

## Journal

- **27/10/2026, vérification indépendante et corrections** : défauts 3 à 8 corrigés (voir « Vérification indépendante du 27/10/2026 »), images reconstruites, migration 0008 sur PostgreSQL, graphe de scoring exécuté pour la première fois dans Airflow, cible optimisée (D48), captures 14 et 15. Au redémarrage, l'ordonnanceur a repris deux exécutions planifiées du graphe des flux, qui ont réécrit les comptes rendus de `results/` sans rien recharger (idempotence observée) ; les comptes rendus de référence ont été restaurés depuis le dépôt et les deux graphes laissés en pause.

- **27/10/2026, module 4a** : agent de pré-remplissage complet, évalué en appel réel sur Claude Haiku 5.5 (clé personnelle, donc en-tête d'espace de travail requis), décisions D41 à D47, leçon sur l'évaluation qui corrige les règles.

- **27/10/2026, module 5** : variables dbt, apprentissage et mesures, scoring mensuel, fiche adhérent, documentation (`docs/eval-resiliation.md`, D33 à D40, leçon du plafond). Adresse PostgreSQL du `Makefile` passée à `127.0.0.1`, et ligne `.PHONY` réparée.

- **22/10/2026, module 6** : README mis à jour (module 3 livré, modules 4 et 5 déclarés non réalisés, preuves du
  module 3, limites), `docs/DEMO.md` (parcours de deux minutes, deux chemins de démarrage), `docs/POUR-LA-DIRECTION.md`,
  dossier `teaser/` (`variables.json`, `figure.py`, `figure.png` tracé depuis `results/powerbi/`). Dans le portfolio :
  fiche `08-courtage-erp.md`, quatre captures et un graphique, fiche d'entretien. Non lancé : `npm run build` du site
  et rendu de la vidéo, qui sont centralisés. Aucune mesure n'a été rejouée, tous les chiffres viennent de `results/`.
- **22/10/2026, recalibrage** : prestations reliées aux cotisations (D32), nouvelle empreinte `ff90a24d…`, ratio
  sinistres sur primes de 76,38 % en 2024 et 79,99 % en 2025. Toutes les preuves, la chaîne de flux, dbt, les
  indicateurs et le projet Power BI ont été rejoués.
- **22/10/2026** : module 3 réalisé. Modèle en étoile complété (cotisations acquises, mouvements, cliché
  mensuel du portefeuille, adhérent, branche), quatre indicateurs définis avec leurs pièges chiffrés, projet
  Power BI PBIP ouvert dans Power BI Desktop et actualisé par commande, 302 comparaisons DAX contre SQL sans
  écart. Défaut préexistant corrigé : le recalcul SQL des commissions ne reprenait pas la règle D24.
  Le moteur Docker a été relancé en démarrant Docker Desktop.

- **20/10/2026** : module 2 réalisé de bout en bout. Générateur de fichiers reçus et manifeste,
  huit contrôles bloquants, rapprochement par référence puis par montant et date, commissions au
  taux daté, bordereaux mensuels, projet dbt en trois couches, graphe Airflow en treize tâches, pile
  Docker complète avec Airflow en exécuteur local. Chaîne exécutée sur SQLite et sur PostgreSQL, et
  par le graphe sur la pile. Le moteur Docker s'est arrêté en fin de session : la capture du graphe
  reste à prendre.

- **19/10/2026, matin** : phase 0 terminée, la note de cadrage métier, conservée hors du dépôt (`docs/CIBLE.md`, exclu par `.gitignore`) écrit. Docker Desktop hors service sur le
  poste, socket de télémétrie périmé.
- **19/10/2026, après-midi** : Docker réparé par Yasmina, vérifié dans la session. Planification écrite
  (`PLAN.md`, `DECISIONS.md`, `HYPOTHESES.md`). Module 1 réalisé de bout en bout : modèle, migrations,
  domaine, générateur, API, interface, tests, preuves sur les deux moteurs, pile Docker exécutée sur le
  poste.
- **19/10/2026** : deux consignes arrivées en cours de module et appliquées, la délégation de gestion au
  modèle (la note de cadrage metier, la note de cadrage métier, conservée hors du dépôt (`docs/CIBLE.md`, exclu par `.gitignore`)) et le chargement des
  skills exacts de `docs/SKILLS.md`.

## Recalibrage de la sinistralité du 22/10/2026

Décision de Yasmina : le ratio sinistres sur primes de 177 % n'était pas plausible, et les chiffres devaient
être corrigés avant la page de présentation. Décision D32.

### Le mécanisme

1. **Les demandes de chaque contrat sont calibrées sur sa cotisation courue** (hors suspension), avec une échelle par
   branche (`ECHELLE_SINISTRALITE` : santé individuelle 1,42, santé collective 1,62), et non par un facteur global.
2. **Chaque contrat tire un multiplicateur de consommation à queue lourde** : 55 % de petits consommateurs, 35 % de
   moyens, 10 % de gros. Mesuré sur 2 066 contrats de 2025 : 8,9 % sans prestation, médiane à 45 % de leur cotisation,
   neuvième décile à 200 %, et 39,9 % des remboursements portés par les 10 % de contrats les plus consommateurs.
3. **Les soins sont tirés sur toute la durée de garantie**, et non sur les quatre premières années du contrat : un contrat
   de 2019 ne consommait plus rien en 2025, ce qui expliquait une partie de l'écart.

### Ce qui n'a pas bougé

Les plafonds annuels cumulés dans l'ordre des dates, l'absence de prestation pendant une suspension et l'absence de
rejet prématuré sont inchangés : les 18 contrôles de cohérence métier passent sur les deux moteurs, avec zéro anomalie
sur ces trois points (`results/coherence_metier.json`). La prévoyance n'a toujours aucune prestation : l'acte n'est pas
délégué, et le ratio publié porte sur les produits à prestations déléguées. Les contrats, avenants, appels,
encaissements, commissions (3 704, 79 346,83 €), rétrocessions, bordereaux, résiliations, production et portefeuille sont
identiques : seules les prestations et ce qui en dépend ont changé.

### Mesures avant et après

| Mesure | Avant | Après | Source |
| --- | --- | --- | --- |
| Prestations (lignes) | 49 398 | 49 970 | `results/generation.json` |
| Empreinte du jeu | `3311d29f…` | `ff90a24d…`, identique sur SQLite et PostgreSQL | `results/reproductibilite_*.json` |
| Ratio 2024 | 177,67 % | 76,38 % | `results/kpi_sql.json` |
| Ratio 2025 | 152,96 % | 79,99 % | idem |
| Ratio 2026, 9 mois | 121,18 % | 72,07 % | idem |
| Santé collective, 2025 | 156,85 % | 79,48 % (75,55 % en 2024) | `results/concordance_dax_sql.csv` |
| Santé individuelle, 2025 | 148,01 % | 80,64 % (77,33 % en 2024) | idem |
| Anomalies d'avertissement des flux | 780 | 621 | `results/flux_journal_lots.json` |
| Concordance DAX contre SQL | 302 comparaisons | 302 comparaisons, écart maximal 2,9e-14 | `results/concordance_dax_sql.json` |

Preuves rejouées : migrations, reproductibilité, cohérence métier, contraintes, mutation (9 défauts sur 9 détectés), chaîne
de flux et idempotence, `dbt build` (199 réussites, 4 avertissements, 0 erreur), indicateurs, projet Power BI actualisé
et évalué, captures des pages Synthèse et Sinistres sur primes reprises. Les pages Résiliations, Production et
Portefeuille n'ont pas changé de chiffres. Trois tests ajoutés dans `tests/test_generation.py` (ratio plausible par
branche et par exercice, dispersion), exécutés sur les deux moteurs.

### Défaut de test révélé par l'intégration continue

`test_archive_ne_recouvre_pas_une_piece_deja_archivee` comparait un lot à `lots[1]`, lu sans `order by` : sur PostgreSQL,
l'ordre des lignes est l'ordre physique et il a changé, le test a échoué dans l'intégration continue alors qu'il passait
sur le poste. Il compare désormais des ensembles de références. C'était un défaut du test, pas du code.

### Ce qui reste

- **Le 2026 de santé individuelle est à 69,62 %**, sous la fourchette de 70 à 85 %, sur 9 mois seulement : ce n'est pas un
  exercice complet, et le calibrage vise les exercices complets.
- **Les prestations de 2020 à 2023 n'ont pas de cotisation en face dans le quittancement** (premier appel du 01/10/2023),
  donc aucun ratio ne peut être lu avant 2024.
- **L'échelle de sinistralité est un paramètre mesuré**, pas une loi : changer les formules ou les plafonds oblige à la
  remesurer.

## Reprise du 21/10/2026 : corrections issues de la vérification indépendante

Ce qui a changé dans les données, et pourquoi. Deux régénérations successives, deux empreintes.

| Empreinte | Lignes | Ce qui l'a fait changer |
| --- | --- | --- |
| `f22fe41f…` | 178 814 | état avant la reprise |
| `a8c542b2…` | 178 086 | le générateur enregistre les suspensions encore ouvertes à la fin de l'historique, et le plafond annuel se consomme dans l'ordre des dates de soins et non dans l'ordre de génération |
| `3311d29f…` | 178 086 | les libellés du référentiel et les commentaires d'avenants sont accentués, et le type d'apporteur `salarie` devient `direct` : ce sont des données, donc l'empreinte change |
| `ff90a24d…` | 178 658 | recalibrage de la sinistralité, 22/10/2026 : les prestations sont calibrées sur la cotisation de chaque contrat (section « Recalibrage de la sinistralité ») |

La reproductibilité n'est pas entamée : deux exécutions de même graine donnent la même empreinte, sur
les deux moteurs. C'est le jeu qui a changé, pas la façon de le produire.

### Défauts corrigés, avec la mesure avant et après

| Défaut | Mesure avant | Mesure après |
| --- | --- | --- |
| Prestations servies pendant une suspension encore ouverte | 6, dont une réglée | 0 |
| Rejets « plafond atteint » tombant avant que le plafond soit consommé | 4 694 | 0 |
| Prestations réglées dépassant le reste de plafond à leur date | 70 | 0 |
| Appels écartés du calcul de commission parce que la compagnie encaisse elle-même | 1 184 sur 3 776, soit 31 % | 0, ils sont commissionnés sur la cotisation appelée |
| Commissions produites sur les trois périodes | 2 520, pour 46 320,66 € | 3 704, pour 79 346,83 € |
| Bordereaux de commissions produits | 6 | 9 |
| Appels déclarés encaissés sans aucun encaissement rattaché, après la chaîne | 11 | 0 |
| Contraintes de porteur unique présentes en base | 0 sur 3 | 3 sur 3, prouvées par insertion SQL directe |
| Mutations couvertes par la preuve par mutation | 6 | 9 |
| Tests couvrant l'alerte sur lot rejeté | 0 | 6 |

### Ce que la chaîne produit sur le jeu régénéré

| Constat | Valeur | Fichier |
| --- | --- | --- |
| Lots reçus | 27, dont 9 rejetés | `results/flux_journal_lots.json` |
| Anomalies bloquantes | 9 | idem |
| Anomalies d'avertissement | 621 | idem |
| Écarts de rapprochement, partiels et écarts | 50 | `results/flux_rapprochement.json` |
| Mouvements qu'aucun appel ne réclame | 24 | idem |
| Appels dont le statut a été redéduit | 11 | idem, champ `appels_reexamines` |
| Commissions, trois périodes | 3 704 pour 79 346,83 € | `results/flux_commissions.json` |
| Rétrocessions | 2 978 pour 38 895,54 € | idem |
| Bordereaux produits | 33, dont 9 de commissions et 24 de rétrocessions | `results/flux_bordereaux.json` |

