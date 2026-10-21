Index des leçons du projet courtage-erp. Une leçon par fichier, un résumé d'une ligne en tête de chaque fichier.

# Leçons apprises

Règle de tenue : mettre à jour une leçon existante plutôt que d'en créer une seconde sur le même sujet,
et supprimer ce qui s'avère faux. Le préfixe `p8` rappelle qu'il s'agit du huitième projet du portfolio.

## Module 1, cœur ERP

| Leçon | Résumé |
| --- | --- |
| [Le schéma doit dire le même métier que la doc](p8-le-schema-doit-dire-le-meme-metier-que-la-doc.md) | La documentation décrivait un appel adressé à l'entreprise, le schéma en adressait un à chaque salarié : c'est le schéma qui avait tort. |
| [Délégation de gestion au modèle](p8-delegation-de-gestion-au-modele.md) | La délégation se modélise en trois tables, et c'est la liste des actes qui fait foi, jamais le libellé de portée. |
| [Reproductibilité et horloge](p8-reproductibilite-et-horloge.md) | Une seule ligne dépendant de `date.today()` rendait fausse la reproductibilité annoncée, et aucune preuve du projet ne pouvait s'en apercevoir. |
| [Un générateur obéit à ses propres règles](p8-un-generateur-doit-obeir-a-ses-propres-regles.md) | Le générateur écrivait des données que l'API aurait refusées, et le test censé le détecter ne regardait que 200 lignes sur 5 777. |
| [Points de reprise SQLite](p8-sqlite-savepoint-pysqlite.md) | Le pilote pysqlite valide la transaction englobante au lieu de relâcher le point de reprise, ce qui fait fuir les données d'un test au suivant. |
| [Connexion d'inspection et DDL](p8-postgres-connexion-inspection-bloque-ddl.md) | Un moteur d'inspection laissé ouvert bloque le DROP TABLE suivant sur PostgreSQL, sans message ni délai d'attente. |
| [Séquences après une reprise](p8-sequences-postgres-apres-reprise.md) | Insérer en fournissant les identifiants ne fait pas avancer les séquences PostgreSQL, et la première écriture applicative échoue. |
| [Alembic ignore les contraintes de vérification](p8-alembic-ignore-les-contraintes-de-verification.md) | Trois règles déclarées dans le modèle n'ont jamais été émises en base, et le test de non-dérive, qui repose sur la même comparaison qu'Alembic, est resté vert. |

## Module 2, flux financiers

| Leçon | Résumé |
| --- | --- |
| [Une mesure de détection se lit contrôle par contrôle](p8-une-mesure-de-detection-se-lit-par-controle.md) | Un rappel et une précision globaux ne veulent rien dire quand les contrôles n'ont pas la même nature : le détail a révélé un contrôle inutilisable que la moyenne cachait. |
| [Orchestrateur et métier ne partagent pas leurs dépendances](p8-orchestrateur-et-metier-ne-partagent-pas-leurs-dependances.md) | Airflow, l'ERP et dbt ne cohabitent pas dans un même environnement Python ; trois environnements isolés et des appels en ligne de commande évitent l'installation qui casse. |

## À lire aussi, hors de ce dépôt

Les leçons des projets précédents du portfolio sont dans `Portfolio/site/docs/lessons/`. Deux sont
directement utiles ici :

- `p3-powerbi-pbip-tmdl.md` et `p3-powerbi-verifier-les-mesures.md`, pour le module 3 : comment produire
  un projet PBIP en TMDL, l'ouvrir dans Power BI Desktop et contrôler chaque mesure DAX contre le SQL.
- `p4-docker-desktop-socket-perime.md`, pour le diagnostic du défaut Docker rencontré le matin du
  19/10/2026 et réparé depuis.
