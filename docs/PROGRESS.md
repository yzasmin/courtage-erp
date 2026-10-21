État réel du projet courtage-erp : ce qui est fait, ce qui reste, et comment reprendre. Mis à jour le 20/10/2026.

# Avancement

## État en une ligne

**Module 1, cœur ERP : fait et prouvé sur les deux moteurs. Module 2, flux financiers : fait et
mesuré.** Reste la capture d'écran du graphe Airflow, qui demande le moteur Docker, arrêté sur ce poste
le 20/10 au soir.

| Étape | État |
| --- | --- |
| 0, connaître la cible | vérifié, 19/10/2026, `la note de cadrage metier, conservee hors du depot` |
| 1, cœur ERP | **fait**, preuves dans `results/` |
| 2, flux financiers Airflow et dbt | **fait**, preuves dans `results/`, une capture d'écran en attente |
| 3, pilotage Power BI | à faire, dépend de l'étape 2 |
| 4a, agent de pré-remplissage | à faire, dépend de l'étape 2 |
| 4b, RAG conditions générales | à faire, si le temps le permet |
| 5, prédiction de résiliation | à faire, dépend de l'étape 2 |
| 6, documentation finale et page de presentation | à faire, en dernier |

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
| Prestations | 49 398 | idem |
| **Total des lignes empreintées** | **178 086** | `results/reproductibilite_sqlite.json` |

Durée de génération : 11,62 s sur SQLite (`results/generation.json`, champ `duree_generation_s`).
La mesure sur PostgreSQL en conteneur n'a pas été reprise après la régénération : elle n'est donc plus
citée ici plutôt que d'être recopiée périmée.

### Preuves du module 1

| Preuve | Résultat | Fichier |
| --- | --- | --- |
| Migrations qui montent et redescendent, SQLite | conforme, 6 révisions, 31 tables, aucun résidu | `results/migrations_sqlite.json` |
| Migrations qui montent et redescendent, PostgreSQL | conforme, 6 révisions, 31 tables, aucun résidu | `results/migrations_postgresql.json` |
| Génération reproductible, SQLite | deux exécutions, empreinte identique | `results/reproductibilite_sqlite.json` |
| Génération reproductible, PostgreSQL | deux exécutions, empreinte identique | `results/reproductibilite_postgresql.json` |
| **Même empreinte sur les deux moteurs** | `3311d29fe0bf7f4c2e2b3d24948fabd5d7021ea814b95cc0447b59acdfa0ed03` | les deux fichiers ci-dessus |
| Suite de tests, base temporaire | 231 passés, 10 sautés | `results/pytest.txt` |
| Suite de tests, base de démonstration | 240 passés, 1 sauté | `results/pytest_base_demonstration.txt` |
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

L'empreinte du jeu de démonstration est passée de `fea8ef82…` à `f22fe41f…`, puis à `3311d29f…`, et le
nombre de lignes de 168 901 à 178 814, puis à 178 086. Les deux derniers changements sont expliqués plus
bas, dans la section « Reprise du 21/10/2026 ». C'est normal et voulu : **les données ont changé parce que le modèle métier a été
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

- **Capture d'écran du graphe Airflow.** Demande le moteur Docker, arrêté sur ce poste. Procédure dans
  `results/airflow_execution.md`. La capture du lineage dbt est faite,
  `docs/captures/07-lineage-dbt-commissions.jpg`.
- **Vérification par un sous-agent à contexte vierge** qui relit la spécification du module 2 et rend
  « critère : conforme ou non conforme : preuve ».

### Modules suivants

Les étapes 3, 4a et 5 ne dépendent plus que du module 2 et ne partagent aucun fichier : elles peuvent
être menées en parallèle. Le modèle en étoile que le module 3 attend existe déjà dans les marts dbt
(`dim_date`, `dim_produit`, `dim_compagnie`, `dim_apporteur`, `fct_cotisations`, `fct_prestations`,
`fct_commissions`), et le tableau de bord Power BI se déclare en exposure à côté des deux déjà
présentes dans `dbt/models/marts/exposures.yml`.

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
| Sortie de `dbt build` | `dbt_build.txt` | 153 réussites, 4 avertissements, 0 erreur |
| Journal d'exécution par lot | `flux_journal_lots.json` | un lot par fichier, avec empreinte, verdict et motif |
| Rapport de détection | `flux_rapport_detection.json` | rappel et précision par code et par sévérité |
| Rejet intégral d'un lot | `flux_rejet_integral.json` | 9 lots rejetés, 0 ligne écrite |
| Idempotence | `flux_idempotence.json` | 27 fichiers redéposés, empreinte d'état identique |
| Rapprochement | `flux_rapprochement.json` | par statut et par méthode |
| Commissions | `flux_commissions.json` | créées, mises à jour, inchangées, et appels écartés avec leur motif |
| Bordereaux | `flux_bordereaux.json` | 6 bordereaux de commissions, 24 de rétrocessions |
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

## Commandes pour reprendre

Sans Docker, sur SQLite, pour développer et tester vite :

```bash
make installer
make regenerer        # redescend le schema, le remonte, regenere le jeu de demonstration
make tests            # 193 tests sur une base temporaire
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

- **20/10/2026** : module 2 réalisé de bout en bout. Générateur de fichiers reçus et manifeste,
  huit contrôles bloquants, rapprochement par référence puis par montant et date, commissions au
  taux daté, bordereaux mensuels, projet dbt en trois couches, graphe Airflow en treize tâches, pile
  Docker complète avec Airflow en exécuteur local. Chaîne exécutée sur SQLite et sur PostgreSQL, et
  par le graphe sur la pile. Le moteur Docker s'est arrêté en fin de session : la capture du graphe
  reste à prendre.

- **19/10/2026, matin** : phase 0 terminée, `la note de cadrage metier, conservee hors du depot` écrit. Docker Desktop hors service sur le
  poste, socket de télémétrie périmé.
- **19/10/2026, après-midi** : Docker réparé par Yasmina, vérifié dans la session. Planification écrite
  (`PLAN.md`, `DECISIONS.md`, `HYPOTHESES.md`). Module 1 réalisé de bout en bout : modèle, migrations,
  domaine, générateur, API, interface, tests, preuves sur les deux moteurs, pile Docker exécutée sur le
  poste.
- **19/10/2026** : deux consignes arrivées en cours de module et appliquées, la délégation de gestion au
  modèle (la note de cadrage metier, `la note de cadrage metier, conservee hors du depot`) et le chargement des
  skills exacts de `docs/SKILLS.md`.

## Reprise du 21/10/2026 : corrections issues de la vérification indépendante

Ce qui a changé dans les données, et pourquoi. Deux régénérations successives, deux empreintes.

| Empreinte | Lignes | Ce qui l'a fait changer |
| --- | --- | --- |
| `f22fe41f…` | 178 814 | état avant la reprise |
| `a8c542b2…` | 178 086 | le générateur enregistre les suspensions encore ouvertes à la fin de l'historique, et le plafond annuel se consomme dans l'ordre des dates de soins et non dans l'ordre de génération |
| `3311d29f…` | 178 086 | les libellés du référentiel et les commentaires d'avenants sont accentués, et le type d'apporteur `salarie` devient `direct` : ce sont des données, donc l'empreinte change |

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
| Anomalies d'avertissement | 780 | idem |
| Écarts de rapprochement, partiels et écarts | 50 | `results/flux_rapprochement.json` |
| Mouvements qu'aucun appel ne réclame | 24 | idem |
| Appels dont le statut a été redéduit | 11 | idem, champ `appels_reexamines` |
| Commissions, trois périodes | 3 704 pour 79 346,83 € | `results/flux_commissions.json` |
| Rétrocessions | 2 978 pour 38 895,54 € | idem |
| Bordereaux produits | 33, dont 9 de commissions et 24 de rétrocessions | `results/flux_bordereaux.json` |

