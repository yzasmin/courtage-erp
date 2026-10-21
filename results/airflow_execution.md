Exécution réelle du graphe Airflow `courtage_flux_financiers` sur la pile Docker de ce poste, le 20/10/2026.

# Exécution du graphe Airflow

## Ce qui a été exécuté

Pile montée par `docker compose up -d --build` : PostgreSQL 16, l'application ERP, le service
`flux-init` qui dépose le courrier simulé, puis `airflow-init`, `airflow-scheduler` et
`airflow-webserver` en exécuteur local, sans Celery ni Redis.

Le graphe a été déclenché à la main :

```bash
docker compose exec airflow-scheduler airflow dags unpause courtage_flux_financiers
docker compose exec airflow-scheduler airflow dags trigger courtage_flux_financiers
```

Exécution `manual__2026-10-20T16:38:13+00:00`, base de données `courtage`.

## États des tâches, relevés pendant l'exécution

Relevés avec `airflow tasks states-for-dag-run courtage_flux_financiers <run_id>` :

| Tâche | État relevé |
| --- | --- |
| `debut` | succès |
| `ingestion.detecter` | succès |
| `ingestion.archiver` | succès |
| `ingestion.charger` | succès |
| `transformer` | succès après correction du sélecteur dbt, voir plus bas |
| `calculs_financiers.rapprocher` | succès, attesté par les bordereaux produits |
| `calculs_financiers.commissions` | succès, attesté par les bordereaux produits |
| `calculs_financiers.bordereaux` | succès, 30 fichiers écrits dans `data/flux/bordereaux/` |
| `publier_les_marts` | succès, marts matérialisées en tables dans la base `courtage` |
| `documenter_le_lineage` | succès, catalogue dbt écrit à 17:06:59 UTC |
| `comptes_rendus.rapport_de_detection` | **non relevé** : le moteur Docker s'est arrêté avant le relevé |
| `comptes_rendus.journal_par_lot` | **non relevé**, même raison |
| `fin` | **non relevé**, même raison |

Le moteur Docker de ce poste s'est arrêté pendant la rédaction de la documentation, après l'étape de
documentation du lineage. Les trois dernières tâches n'ont donc pas pu être relevées, et la capture
d'écran du graphe reste à prendre. Les sorties de ces trois tâches existent par ailleurs, produites par
la même chaîne lancée en ligne de commande sur PostgreSQL : voir `flux_rapport_detection.json` et
`flux_journal_lots.json`.

## Ce que l'exécution a laissé sur le disque

Artefacts écrits par les conteneurs dans les volumes partagés, donc vérifiables sans Docker :

| Constat | Valeur | Comment le revérifier |
| --- | --- | --- |
| lots archivés | 27 | `find data/flux/archive -type f \| wc -l` |
| dossier d'arrivée vidé | 0 fichier restant | `ls data/flux/arrivee` |
| lots rejetés, copiés pour l'émetteur | 9 | `ls data/flux/rejets` |
| bordereaux produits | 30 fichiers CSV | `find data/flux/bordereaux -name "*.csv" \| wc -l` |
| marts matérialisées | tables dans `courtage.analytique_marts` | `dbt/cible/catalog.json` |
| catalogue dbt produit par le graphe | 157 objets, 20/10/2026 17:06:59 UTC | `dbt/cible/catalog.json` |

Les neuf lots rejetés, tels que le graphe les a laissés dans `data/flux/rejets/` :

```
COTISATIONS_LIT_202607_copie.xlsx    empreinte déjà chargée
COTISATIONS_LIT_202608.xlsx          acte non délégué
COTISATIONS_OCE_202607.csv           contrat inconnu
COTISATIONS_OCE_202608.csv           doublon de clé métier
COTISATIONS_OCE_202609.csv           schéma invalide, date impossible
ENCAISSEMENTS_BANQUE_202609.csv      schéma invalide, montant non numérique
PRESTATIONS_OCE_202607.csv           total incohérent
PRESTATIONS_OCE_202608.csv           période incohérente
PRESTATIONS_OCE_202609.csv           adhérent inconnu
```

Les motifs ci-dessus sont ceux mesurés par la même chaîne sur PostgreSQL, dans
`flux_rapport_detection.json`, section `lots_rejetes`.

## Deux défauts trouvés en exécutant le graphe, et corrigés

Aucun des deux n'avait été vu en relisant le code.

**Le dossier des comptes rendus était déduit de l'emplacement du module.** Dans un dépôt cloné,
`RACINE_PROJET` vaut bien la racine du dépôt ; pour un paquet **installé**, elle vaut le dossier des
bibliothèques de l'environnement virtuel. Les comptes rendus des tâches atterrissaient donc dans
l'environnement virtuel du conteneur, hors de tout volume, et disparaissaient avec lui. Le dossier est
désormais lu dans la variable `COURTAGE_RESULTATS`.

**Le sélecteur dbt de la première tâche de transformation retenait trop de tests.** Par défaut, dbt
retient un test dès qu'**un seul** de ses parents est sélectionné. Les tests qui comparent un modèle de
staging à un mart étaient donc exécutés avant que les marts n'existent, et la tâche échouait sur une
relation absente. `--indirect-selection cautious` ne retient un test que si **tous** ses parents sont
sélectionnés, ce qui est la sémantique voulue.

Un troisième défaut, de permissions, a été corrigé au passage : l'image de l'ERP tourne sous
l'utilisateur 10001 et celle d'Airflow sous 50000, et les deux partagent le dossier des flux. Les
fichiers déposés par le premier n'étaient pas déplaçables par le second, et l'archivage échouait. Le
service `flux-init` tourne désormais sous le même identifiant qu'Airflow.

## Ce qui reste à faire

La capture d'écran du graphe dans l'interface Airflow. Elle demande le moteur Docker, actuellement
arrêté sur ce poste. Procédure, une fois Docker redémarré :

```bash
docker compose up -d
# interface : http://localhost:8080, compte admin, mot de passe du fichier .env
docker compose exec airflow-scheduler airflow dags trigger courtage_flux_financiers
```

La vue « Graph » de l'exécution donne la capture attendue pour la page portfolio.
