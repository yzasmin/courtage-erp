Une ligne par décision technique : le choix retenu, l'alternative écartée, la raison. Lisible par un dirigeant.

# Décisions techniques

Les choix imposés par la spécification (Airflow, dbt, Power BI, données synthétiques déterministes,
démarrage en une commande) ne sont pas rediscutés ici. Ce fichier ne consigne que les choix libres.

## Socle technique, arrêtés le 19/10/2026

| Décision | Choix retenu | Alternative écartée | Raison |
| --- | --- | --- | --- |
| D01 Langage | Python 3.12 | Java ou C# | Un seul langage du cœur ERP au modèle de résiliation : l'orchestration Airflow, dbt, l'extraction de documents et l'apprentissage automatique vivent déjà dans cet écosystème. Les six modules partagent donc un environnement au lieu de deux. |
| D02 Base de production | PostgreSQL 16 | MySQL ou SQL Server | Contraintes de vérification et clés étrangères différées fiables, types date et numérique rigoureux, et c'est la base déjà montée pour les métadonnées d'Airflow : un seul service pour deux usages sur un poste de 8 Go. |
| D03 Base de développement | SQLite, même code | PostgreSQL seul | Les tests tournent en quelques secondes sans conteneur, ce qui permet d'avancer et laisse un relecteur sans Docker exécuter la suite. Le risque de divergence est traité par D04 et prouvé en exécutant migrations, génération et tests sur les deux moteurs. |
| D04 Accès aux données | SQLAlchemy 2.0, couche ORM typée | SQL écrit à la main par moteur | Un seul jeu de modèles produit le schéma des deux moteurs, donc une seule définition de l'intégrité. Le SQL reste écrit à la main là où il est le plus lisible, dans les requêtes de contrôle des indicateurs du module 3. |
| D05 Migrations | Alembic, une révision par changement | `create_all` au démarrage | La spécification exige des migrations qui montent et descendent. Alembic donne une révision versionnée, réversible et rejouable, ce qu'un éditeur installant son produit chez ses clients attend d'une reprise de schéma. |
| D06 Montants | Entiers de centimes en base, euros à l'affichage | Nombres à virgule flottante | Un centime perdu par arrondi sur un bordereau de commissions est une anomalie comptable. L'entier supprime la dérive, et il se comporte à l'identique sur PostgreSQL et SQLite, ce que le type numérique ne fait pas. |
| D07 Cadriciel d'API | FastAPI et Pydantic v2 | Django REST Framework | La documentation OpenAPI est produite par le code lui-même, donc elle ne peut pas mentir, et la validation stricte de Pydantic sert aussi de garde-fou à la sortie structurée du modèle de langage au module 4. |
| D08 Interface | Gabarits Jinja2 et HTMX, servis par la même application | Application React séparée | Un écran de gestionnaire est une liste, une fiche et un formulaire : HTMX suffit. Aucune chaîne de compilation Node à installer ni à maintenir, un seul processus à démarrer pour la démonstration, et le poste économise la mémoire d'un serveur de développement. |
| D09 Génération de données | `random.Random` à graine fixe, par lots | NumPy ou Faker | Le tirage de la bibliothèque standard est reproductible sans dépendance supplémentaire, et l'écriture par lots tient dans la mémoire disponible. La reproductibilité est prouvée par une empreinte SHA-256 du jeu produit. |
| D10 Historisation | Avenants datés, état reconstitué par repli | Table d'historique, ou extensions temporelles | L'avenant est l'objet que le métier manipule déjà. Le faire porter l'historique évite d'inventer une seconde vérité, et la reconstitution à une date est alors une simple lecture du dernier avenant en vigueur. |
| D11 Tests | pytest, exécuté sur SQLite et sur PostgreSQL | pytest sur SQLite seulement | Le même code devant tourner sur les deux moteurs, la suite doit le vérifier sur les deux, sinon la portabilité n'est qu'une affirmation. |
| D12 Style | ruff, configuration reprise de radar-entreprises | flake8 et black | Même verdict sur le poste et en intégration continue, et la cohérence avec les autres projets du portfolio évite un second jeu de conventions. |
| D13 Interface de modèle de langage (module 4) | Interface commune, trois implémentations : Ollama local, fournisseur distant, rejeu enregistré | Appel direct à un fournisseur | Aucune clé d'API n'est disponible aujourd'hui, et la spécification exige que les tests passent sans clé. Le rejeu enregistré rend la suite déterministe et gratuite, les deux autres implémentations servent la démonstration. |

## Dimensionnement des conteneurs

Mesuré sur ce poste le 19/10/2026 : `docker info` annonce 8 processeurs et 4 031 537 152 octets, soit
environ 3,75 Go pour la machine virtuelle Docker. La mémoire physique libre côté Windows était de
807 544 Ko au même moment.

| Décision | Choix retenu | Alternative écartée | Raison |
| --- | --- | --- | --- |
| D14 Exécuteur Airflow | `LocalExecutor` | `CeleryExecutor` | Celery impose Redis et des processus de travail séparés, soit deux services de plus pour une charge qui tient dans un seul processus. Les 3,75 Go de la machine virtuelle ne le permettent pas et le métier ne le demande pas. |
| D15 Limites mémoire | Déclarées service par service dans `docker-compose.yml` | Pas de limite | Sans limite explicite, un ordonnanceur qui gonfle fait tomber le poste entier. Les valeurs retenues sont mesurées avec `docker stats` et consignées ci-dessous. |
| D16 Base de l'ERP et base d'Airflow | Un seul service PostgreSQL, deux bases distinctes | Deux services PostgreSQL | Un seul moteur à démarrer, donc un seul coût mémoire fixe, tout en gardant les métadonnées d'Airflow séparées des données métier. |

### Empreinte mémoire réelle de la pile complète, mesurée le 20/10/2026

Mesure prise avec `docker stats --no-stream`, pile entière démarrée et graphe Airflow en cours
d'exécution, donc au moment le plus chargé. Machine virtuelle Docker de 4 031 537 152 octets, soit
environ 3,75 Go (`docker info`).

| Conteneur | Mémoire utilisée | Limite déclarée | Part de la limite |
| --- | --- | --- | --- |
| Serveur web Airflow | 706,6 Mio | 768 Mio, portée depuis à 1 024 Mio | 92,0 % |
| Ordonnanceur Airflow | 577,9 Mio | 768 Mio | 75,3 % |
| PostgreSQL | 197,3 Mio | 512 Mio | 38,5 % |
| Application ERP | 85,0 Mio | 512 Mio | 16,6 % |
| **Total** | **environ 1 567 Mio** | | **environ 40,8 % de la machine virtuelle** |

La part est calculée sur les 4 031 537 152 octets de la machine virtuelle, soit 3 844,8 Mio :
1 567 divisé par 3 844,8 donne 40,8 pour cent. Le document annonçait 42 pour cent, chiffre qu'aucun
calcul ne reproduisait.

Conséquence tirée de la mesure, et c'est la raison d'être de ce tableau : le serveur web occupait
92 pour cent de sa limite, ce qui l'expose à une interruption par le noyau au premier pic. Sa limite a
donc été dissociée de celle de l'ordonnanceur et portée à 1 024 Mio. Les deux services n'ont pas le
même profil, les aligner sur la valeur la plus basse était une erreur de dimensionnement.

| Décision | Choix retenu | Alternative écartée | Raison |
| --- | --- | --- | --- |
| D17 Limite du serveur web Airflow | 1 024 Mio, distincte de celle de l'ordonnanceur | Une limite unique pour les deux | Mesure à l'appui : 706,6 Mio pour le serveur web contre 577,9 Mio pour l'ordonnanceur. Une limite commune calée sur le plus gros gaspille, calée sur le plus petit tue le service. |
| D18 Isolation des environnements Python dans l'image Airflow | Trois environnements virtuels : Airflow, le client métier, dbt | Un seul environnement partagé | Airflow contraint strictement ses dépendances et impose encore SQLAlchemy 1.4, l'application ERP utilise SQLAlchemy 2, dbt impose ses versions de Jinja et de protobuf. Une résolution unique tient le jour de l'installation et casse à la première montée de version. Le graphe appelle donc des exécutables et lit un code de retour. |
| D19 Dossier des comptes rendus | Lu dans `COURTAGE_RESULTATS`, racine du dépôt par défaut | Déduit de l'emplacement du module | Défaut constaté en exécutant le graphe : pour un paquet installé, la racine déduite est le dossier des bibliothèques de l'environnement virtuel, et les comptes rendus disparaissaient avec le conteneur. |
| D20 Identifiant d'utilisateur du service de génération des flux | Le même que celui d'Airflow | Celui de l'image de l'ERP | Les deux conteneurs partagent le dossier des flux : l'un dépose, l'autre archive. Des fichiers écrits sous 10001 ne sont pas déplaçables sous 50000, et l'archivage échouait sur une permission refusée. |
| D21 Référence d'un lot reçu | Nom du fichier suivi du début de son empreinte | Nom du fichier seul | Une compagnie qui renvoie son bordereau corrigé **sous le même nom** produit un contenu différent, donc un nouveau lot, dont la référence entrait en collision avec celle du premier. La référence désigne désormais le contenu reçu, pas le nom du fichier, et le journal montre les deux envois côte à côte. |
| D22 Émetteur du bordereau de prestations | Le concentrateur de tiers payant, par flux de retour vers le délégataire | La compagnie, comme la documentation l'écrivait d'abord | Une compagnie qui a délégué la gestion des prestations ne les gère plus : elle n'en a pas le détail et ne peut pas en envoyer le bordereau. Le flux entrant vient du concentrateur ; le bordereau que le cabinet émet vers la compagnie pour se faire rembourser est un flux **sortant**, non modélisé, voir D23. |
| D23 Bordereau de prestations émis vers la compagnie | Hors périmètre du module 2 | Le modéliser comme quatrième flux | Le module traite le contrôle de ce que le cabinet **reçoit**, qui est le sujet du rejet intégral et du rapprochement. Un flux sortant n'a ni contrôle d'entrée ni rapprochement bancaire : il doublerait le volume de code sans rien démontrer de plus. Limite assumée et écrite comme telle. |
| D24 Commission quand la compagnie encaisse elle-même | Commissionner sur la **cotisation appelée hors taxe**, et compter le cas à part | Écarter ces appels, comme avant | Un courtier dont la compagnie encaisse directement est commissionné quand même : la compagnie encaisse, calcule la commission due et la verse avec son bordereau de commissions. Les écarter faisait disparaître 31 pour cent du portefeuille des bordereaux, soit 1 184 appels sur 3 776. L'assiette appelée est la meilleure assiette observable par le cabinet sur ces produits. |
| D25 Bordereau de commissions reçu de la compagnie | Hors périmètre, et déclaré tel quel | L'ingérer comme quatrième flux entrant | Ce serait la source qui fait foi sur les produits de D24, et le calcul deviendrait une attente à rapprocher. Le rapprochement commission attendue contre commission versée est un module à part entière ; l'annoncer sans le faire serait pire que de poser la limite. |

## Module 3, pilotage

| Décision | Choix retenu | Alternative écartée | Raison |
| --- | --- | --- | --- |
| D26 Cotisations acquises | Fait dédié `fct_cotisations_acquises`, un appel par mois couvert, réparti au prorata des jours en dbt | Répartir dans le DAX à chaque évaluation, ou prendre les cotisations émises | Le ratio sinistres sur primes exige des cotisations acquises. Les émises donnent 133,27 % au lieu de 121,18 % en 2026. Répartie une fois en dbt et testée (somme des parts égale à l'appel), la cotisation acquise se lit en une somme. |
| D27 Portefeuille à une date | Cliché de fin de mois, une ligne par contrat (`fct_portefeuille_mensuel`), reconstitué depuis les avenants datés | Calcul à la volée dans le DAX, ou lecture du statut courant | Le statut courant ne dit rien du passé. Le cliché permet de lire l'effectif de début de période, dénominateur du taux de résiliation, et une identité stock et flux la teste. |
| D28 Rattachement des mouvements | Apporteur et cotisation de la version du contrat au jour du mouvement | Apporteur et cotisation courants du contrat | En 2025, 26 des 834 affaires ont changé d'apporteur depuis, et la cotisation courante gonfle la production de 37 161,60 €. |
| D29 Source de Power BI | CSV exportés des marts, chemin passé en paramètre | Connexion directe à PostgreSQL | Le projet s'ouvre sans pilote ni identifiant ; le coût est un chemin absolu à adapter après un clone, documenté. |
| D30 Périmètre du ratio sinistres sur primes | Produits dont une convention de délégation en vigueur confie la gestion des prestations, lu dans `dim_produit` | Tous les produits | La prévoyance a des cotisations et aucune prestation chez le cabinet : tous produits, le ratio de 2025 tombe de 152,96 % à 109,67 %. |
| D31 Recalcul SQL des commissions | Reprend la règle D24 : repli sur la cotisation appelée hors taxe quand l'encaissement n'est pas délégué ; matérialisé en table | Laisser le recalcul en vue sans la règle | Défaut préexistant trouvé par le module 3 : le contrôle ignorait D24 et deux tests échouaient sur 1 184 appels. La table évite une dérive du plan (24 minutes mesurées sur une vue). Voir `docs/lessons/p8-sql-et-application-appliquent-la-meme-regle.md`. |

## Journal des contraintes de la machine

| Date | Constat | Conséquence |
| --- | --- | --- |
| 19/10/2026, matin | Docker Desktop ne démarrait pas : socket de télémétrie périmé, moteur sans tube nommé. Aucune distribution Linux complète sous WSL. | La plateforme devait être écrite pour `docker compose up` et prouvée uniquement en intégration continue, comme les projets 4 et 7 du portfolio. |
| 20/10/2026, soir | Le moteur Docker s'est arrêté en cours de session : les processus de Docker Desktop tournaient encore, mais le service `com.docker.service` était à l'arrêt et le tube nommé absent. | La capture d'écran du graphe Airflow reste à prendre. Le redémarrage d'un service Windows demande Yasmina. Tout le reste du module 2 a été produit et mesuré avant l'arrêt, et les artefacts écrits dans les volumes partagés restent vérifiables sans Docker. |
| 19/10/2026, après-midi | Docker Desktop réparé par Yasmina. Vérifié dans cette session : `docker info` répond 29.8.2, conteneurs Linux, 8 processeurs, 4 031 537 152 octets ; `docker compose version` répond v5.6.0. | `docker compose up` devient la démonstration locale réelle, exécutée sur ce poste. L'intégration continue reste la preuve reproductible pour un lecteur extérieur, mais elle n'est plus le seul chemin. Le principe « tout ce qui peut tourner nativement en Python tourne aussi sans Docker » est conservé, pour les tests rapides et pour un relecteur sans Docker. |
