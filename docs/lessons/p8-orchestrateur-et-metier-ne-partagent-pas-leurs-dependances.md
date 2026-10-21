Airflow, l'application ERP et dbt ne peuvent pas cohabiter dans un même environnement Python : trois environnements isolés et des appels en ligne de commande coûtent un peu de disque et évitent une installation qui casse à la première montée de version.

# Un orchestrateur et le code métier ne partagent pas leurs dépendances

## Le constat

Le réflexe, quand on écrit un graphe Airflow, est d'importer le code métier et d'appeler ses fonctions
depuis un `PythonOperator`. C'est plus court à écrire, et c'est ce que montrent la plupart des exemples.

Sur ce projet, c'était impossible, et la raison est banale :

- Airflow 2.10 impose encore SQLAlchemy 1.4 ;
- l'application ERP utilise SQLAlchemy 2, et s'appuie sur sa syntaxe de requêtes ;
- dbt impose ses propres versions de Jinja, de protobuf et de `click`.

Un environnement unique qui satisfait les trois n'existe pas aujourd'hui, et s'il existait, il tiendrait
le jour de l'installation et casserait à la première montée de version de l'un des trois. C'est la cause
la plus banale des installations d'Airflow qui ne se mettent plus à jour.

## Ce qui a été fait

Trois environnements virtuels dans la même image, et aucun import entre eux :

```
/home/airflow/.local   Airflow et ses dépendances
/opt/courtage-venv     le paquet `courtage`, installé depuis les sources du dépôt
/opt/dbt-venv          dbt-core et dbt-postgres
```

Chaque tâche du graphe est un `BashOperator` qui appelle un exécutable et lit un code de retour. Le
graphe ne sait rien du métier : il sait qu'une commande a réussi ou échoué.

## Ce que cela coûte, ce que cela rapporte

Le coût est réel et il faut l'assumer : un peu de place disque, et la perte des XCom pour passer des
valeurs entre tâches. Sur cette chaîne, l'état circule par la base, dans la colonne `statut` de la table
des lots, ce qui est de toute façon plus solide qu'un XCom pour une reprise après incident.

Ce que cela rapporte, dans l'ordre d'importance :

1. **L'orchestrateur se met à jour sans toucher au métier**, et réciproquement.
2. **Chaque étape s'exécute à la main, sur un poste sans Airflow.** C'est ce qui permet à la suite de
   tests de vérifier le rejet intégral d'un lot et l'idempotence en quelques secondes, au lieu de monter
   une pile de conteneurs.
3. **Un échec de dépendance ne peut pas rendre le graphe illisible.** Le fichier du graphe n'importe que
   des modules d'Airflow.

## Trois défauts que seule l'exécution a révélés

Aucun n'était visible à la relecture, et tous les trois venaient de la frontière entre les conteneurs.

**Le dossier des comptes rendus était déduit de l'emplacement du module.** Le code calculait la racine
du projet à partir de `__file__`. Dans un dépôt cloné, cela donne bien la racine du dépôt ; pour un
paquet **installé**, cela donne le dossier des bibliothèques de l'environnement virtuel. Les comptes
rendus des tâches atterrissaient donc dans l'environnement virtuel du conteneur, hors de tout volume, et
disparaissaient avec lui. Le dossier est désormais lu dans une variable d'environnement.

**Deux conteneurs qui partagent un volume doivent partager un identifiant d'utilisateur.** L'image de
l'ERP tourne sous l'utilisateur 10001, celle d'Airflow sous 50000. Le premier déposait les fichiers dans
le dossier d'arrivée, le second devait les déplacer dans l'archive, et échouait sur une permission
refusée. Les fichiers appartenaient à 10001, le dossier aussi, et 50000 ne pouvait pas y supprimer une
entrée.

**Une construction d'image qui change d'utilisateur doit préparer ses dossiers avant.** Sous `/opt`,
seul root écrit par défaut. Créer un environnement virtuel après avoir rendu la main à l'utilisateur
non privilégié échoue sur une permission refusée. Les dossiers sont créés et donnés à l'utilisateur
pendant qu'on est encore root, et la main est rendue juste après.

## Un quatrième défaut, propre à dbt

La première tâche de transformation construit les couches staging et intermédiaire, avant que les
calculs financiers ne remplissent les tables de commissions. Elle échouait sur une relation absente.

La cause : par défaut, dbt retient un test dès qu'**un seul** de ses parents est sélectionné. Les tests
qui comparent un modèle de staging à un mart étaient donc exécutés à ce stade, alors que les marts
n'existaient pas encore. `--indirect-selection cautious` ne retient un test que si **tous** ses parents
sont sélectionnés, ce qui est la sémantique voulue ici.

## Où regarder dans le dépôt

- `docker/Dockerfile.airflow`, pour les trois environnements et l'ordre des droits.
- `dags/courtage_flux_financiers.py`, pour les appels en ligne de commande et les sélecteurs dbt.
- `docker-compose.yml`, services `flux-init` et `airflow-*`, pour l'identifiant partagé et les volumes.
