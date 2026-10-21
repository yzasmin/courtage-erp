"""Graphe des flux financiers : detection, archivage, chargement, dbt, rapprochement, commissions.

Ce que ce graphe automatise, en termes de gestion : le courrier financier du mois. Les compagnies
envoient leurs bordereaux de cotisations et de prestations, la banque son releve, et le cabinet doit en
tirer trois choses avant de pouvoir facturer quoi que ce soit : savoir quelles cotisations appelees ont
ete reellement encaissees, calculer les commissions que les compagnies lui doivent, et editer le
bordereau de retrocession de chacun de ses apporteurs.

**Pourquoi des commandes et non du code importe.** Chaque tache appelle un executable dans un
environnement virtuel dedie, `courtage` pour la chaine metier et `dbt` pour les transformations. Airflow
contraint strictement ses propres dependances, et l'application ERP utilise SQLAlchemy 2 ; les faire
cohabiter dans un meme environnement rend l'installation fragile et la premiere montee de version la
casse. Ici les deux mondes ne se rencontrent qu'a travers une ligne de commande et un code de retour.
Consequence utile : chaque tache s'execute aussi a la main, sur un poste sans Airflow.

**Pourquoi quatorze taches et non une.** Le decompte exact, parce qu'il a deja ete documente faux :
`debut` et `fin`, trois taches d'ingestion, `transformer`, trois taches de calculs financiers,
`publier_les_marts`, `documenter_le_lineage`, et trois comptes rendus, soit quatorze au total. Les
groupes de taches en rassemblent une partie sous trois blocs dans l'interface ; un bloc n'est pas une
tache. La commande `airflow tasks list courtage_flux_financiers` donne la liste qui fait foi.

Chacune echoue pour une raison differente et se reprend a un
endroit different. Un depot incomplet fait echouer l'archivage, une base indisponible fait echouer le
chargement, un modele dbt casse fait echouer les transformations. L'etat d'avancement est porte par la
colonne `statut` de `lot_fichier`, donc une reprise apres echec reprend chaque lot ou il en etait au
lieu de recommencer au depot.

**Ordre des etapes**, celui que la specification impose :

1. `detecter`     inscrit au journal les fichiers presents, avec leur empreinte SHA-256
2. `archiver`     deplace le brut dans l'archive et verifie que l'empreinte n'a pas change
3. `charger`      applique les controles, puis charge la couche brute **ou** rejette le lot entier
4. `transformer`  `dbt build` des couches staging et intermediaire, avec leurs tests de qualite
5. `rapprocher`   par reference, puis par montant et date dans une fenetre parametrable
6. `commissions`  au taux valide a la date d'echeance, sur la cotisation encaissee
7. `bordereaux`   bordereaux mensuels, par compagnie et par apporteur, en base et en CSV
8. `publier`      `dbt build` des marts, qui doivent refleter les commissions venant d'etre calculees
9. `documenter`   `dbt docs generate` pour la documentation et le lineage
10. `rapport`     rappel et precision des anomalies contre le manifeste
11. `journal`     journal d'execution par lot, reconstruit depuis la base
12. `alerter`     **echoue** si le depot du jour contient un lot rejete, pour que le rejet se voie

L'etape 8 vient apres le calcul des commissions, et pas avant, pour une raison simple : les marts
exposent les commissions. Les construire avant le calcul les publierait vides au premier passage du
mois.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.task_group import TaskGroup

#: Executable du client metier, installe dans son propre environnement virtuel par l'image.
COURTAGE = os.environ.get("COURTAGE_EXECUTABLE", "/opt/courtage-venv/bin/courtage")
#: Executable dbt, dans un environnement virtuel separe de celui d'Airflow et de celui de l'ERP.
DBT = os.environ.get("DBT_EXECUTABLE", "/opt/dbt-venv/bin/dbt")
#: Racine du projet dbt.
PROJET_DBT = os.environ.get("DBT_PROJET", "/opt/courtage/dbt")

#: Fenetre de tolerance du rapprochement par montant et date, en jours. Parametrable par variable
#: d'environnement, comme la specification l'exige, sans toucher au graphe.
FENETRE_JOURS = os.environ.get("COURTAGE_FENETRE_RAPPROCHEMENT_JOURS", "15")

#: Options communes a tous les appels dbt. `--fail-fast` arrete le build au premier modele en echec :
#: sur une chaine financiere, continuer apres un modele casse construirait des marts a partir de
#: donnees incompletes, ce qui est pire qu'un graphe rouge.
DBT_COMMUN = f"--project-dir {PROJET_DBT} --profiles-dir {PROJET_DBT} --no-use-colors"


def _dbt(commande: str) -> str:
    """Compose une commande dbt complete, journalisee telle quelle dans les logs de la tache."""
    return f"{DBT} {commande} {DBT_COMMUN}"


#: Reglages par defaut de toutes les taches.
#:
#: `retries` a deux avec un delai de deux minutes : les echecs reels de cette chaine sont des echecs
#: transitoires, une base qui redemarre ou un fichier encore en cours d'ecriture. Un echec metier, lui,
#: n'est pas reessaye utilement : un lot rejete reste rejete, et le rejet n'est pas un echec de tache.
REGLAGES_PAR_DEFAUT = {
    "owner": "cabinet-grossiste",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "execution_timeout": timedelta(minutes=30),
    "depends_on_past": False,
    "email_on_failure": False,
}

with DAG(
    dag_id="courtage_flux_financiers",
    description=(
        "Flux financiers du cabinet : bordereaux recus, controles bloquants, rapprochement des"
        " cotisations, commissions et bordereaux de retrocession"
    ),
    doc_md=__doc__,
    default_args=REGLAGES_PAR_DEFAUT,
    # Deux heures du matin : les depots des compagnies arrivent dans la nuit, et la chaine doit avoir
    # fini avant l'ouverture du cabinet.
    schedule="0 2 * * *",
    start_date=datetime(2026, 7, 1),
    # Pas de rattrapage : la chaine traite le dossier d'arrivee tel qu'il est, elle ne rejoue pas un
    # etat passe. Lancer trente executions de rattrapage ne ferait que relire trente fois le meme
    # dossier, et les vingt-neuf dernieres ne trouveraient rien a faire.
    catchup=False,
    # Une execution a la fois : deux executions concurrentes se disputeraient les memes fichiers.
    max_active_runs=1,
    tags=["courtage", "flux-financiers", "module-2"],
) as graphe:
    debut = EmptyOperator(task_id="debut")

    with TaskGroup(
        group_id="ingestion",
        tooltip="Du fichier depose a la couche brute, avec rejet integral des lots fautifs",
    ) as ingestion:
        detecter = BashOperator(
            task_id="detecter",
            bash_command=f"{COURTAGE} flux detecter",
            doc_md=(
                "Inscrit au journal chaque fichier present dans le dossier d'arrivee, avec son"
                " empreinte SHA-256. Rejouer cette tache sur un dossier inchange n'ajoute rien :"
                " l'unicite du couple empreinte et nom de fichier l'interdit en base."
            ),
        )
        archiver = BashOperator(
            task_id="archiver",
            bash_command=f"{COURTAGE} flux archiver",
            doc_md=(
                "Deplace le brut dans l'archive et verifie que l'empreinte n'a pas change pendant le"
                " deplacement. Un fichier archive n'est plus jamais modifie : c'est la piece d'audit."
            ),
        )
        charger = BashOperator(
            task_id="charger",
            bash_command=f"{COURTAGE} flux charger",
            doc_md=(
                "Applique les huit controles bloquants et les deux controles non bloquants, puis charge"
                " la couche brute **ou** rejette le lot entier. Les controles sont executes en totalite"
                " avant la premiere ecriture : un lot rejete n'a donc pas d'ecriture a annuler. Un lot,"
                " une transaction, pour que le rejet d'un bordereau ne bloque pas les autres."
            ),
        )
        detecter >> archiver >> charger

    transformer = BashOperator(
        task_id="transformer",
        bash_command=_dbt(
            "build --fail-fast --indirect-selection cautious --select staging intermediaire"
        ),
        doc_md=(
            "`dbt build` des couches staging et intermediaire : les modeles et leurs tests dans le meme"
            " passage, pour valider la couche brute **avant** de calculer de l'argent.\n\n"
            "`--indirect-selection cautious` n'est pas un detail. Par defaut, dbt retient un test des"
            " qu'**un seul** de ses parents est selectionne : les tests qui comparent un modele de"
            " staging a un mart etaient donc executes a ce stade, alors que les marts n'existent pas"
            " encore, et le graphe echouait sur une relation absente. Le mode prudent ne retient un"
            " test que si **tous** ses parents sont selectionnes, ce qui est la semantique voulue ici."
            " Defaut constate en executant le graphe, pas en relisant le code."
        ),
    )

    with TaskGroup(
        group_id="calculs_financiers",
        tooltip="Rapprochement, commissions, retrocessions et bordereaux mensuels",
    ) as calculs:
        rapprocher = BashOperator(
            task_id="rapprocher",
            bash_command=f"{COURTAGE} flux rapprocher --fenetre-jours {FENETRE_JOURS}",
            doc_md=(
                "Rapproche chaque mouvement bancaire avec un appel de cotisation, d'abord par"
                " reference, puis par montant et date dans la fenetre de tolerance. La delegation de"
                " gestion est opposee avant tout traitement : un mouvement rattache a un contrat dont"
                " la compagnie n'a pas delegue l'encaissement n'est pas rapproche, meme si le fichier"
                " le contient."
            ),
        )
        commissions = BashOperator(
            task_id="commissions",
            bash_command=f"{COURTAGE} flux commissions",
            doc_md=(
                "Calcule la commission due par la compagnie et la retrocession due a l'apporteur, au"
                " taux en vigueur a la date d'echeance de l'appel et non a celui d'aujourd'hui."
            ),
        )
        bordereaux = BashOperator(
            task_id="bordereaux",
            bash_command=f"{COURTAGE} flux bordereaux",
            doc_md=(
                "Edite les bordereaux mensuels, un par compagnie pour les commissions et un par"
                " apporteur pour les retrocessions, en base et en CSV."
            ),
        )
        rapprocher >> commissions >> bordereaux

    publier = BashOperator(
        task_id="publier_les_marts",
        bash_command=_dbt("build --fail-fast"),
        doc_md=(
            "`dbt build` complet, apres le calcul des commissions et non avant : les marts exposent les"
            " commissions, et les construire plus tot les publierait vides.\n\n"
            "Complet, et non limite aux marts, pour que **tous** les tests s'executent une fois que"
            " tous les modeles existent. Les modeles de staging et d'intermediaire etant deja"
            " construits, le cout de ce second passage est celui de leur rafraichissement, negligeable"
            " sur ce volume. Un test qui ne tourne jamais ne protege de rien."
        ),
    )

    documenter = BashOperator(
        task_id="documenter_le_lineage",
        bash_command=_dbt("docs generate"),
        doc_md="Produit la documentation dbt et le graphe de lineage, servis par `dbt docs serve`.",
    )

    with TaskGroup(group_id="comptes_rendus", tooltip="Preuves exploitables du passage") as comptes_rendus:
        rapport = BashOperator(
            task_id="rapport_de_detection",
            bash_command=f"{COURTAGE} flux rapport",
            doc_md=(
                "Compare les anomalies detectees au manifeste de verite terrain et publie le rappel et"
                " la precision reellement calcules, code par code."
            ),
        )
        journal = BashOperator(
            task_id="journal_par_lot",
            bash_command=f"{COURTAGE} flux journal",
            doc_md=(
                "Reconstruit le journal d'execution par lot depuis la base : empreinte, archive,"
                " verdict, lignes chargees et motif de rejet."
            ),
        )
        alerter = BashOperator(
            task_id="alerter_sur_les_lots_rejetes",
            bash_command=f"{COURTAGE} flux alerter",
            # Aucune reprise. Rejouer un rejet metier ne changerait rien : la correction vient de
            # l'emetteur, qui renvoie un fichier different, donc un autre lot. Deux reessais ne
            # feraient que retarder l'alerte de quatre minutes.
            retries=0,
            doc_md=(
                "**Cette tache echoue volontairement quand un lot a ete rejete**, et c'est le"
                " mecanisme par lequel un rejet devient visible dans Airflow.\n\n"
                "Pourquoi ici et pas dans `charger`. Un lot rejete n'est pas un echec technique : les"
                " controles ont fait leur travail, les autres lots du meme depot ont ete charges, et"
                " les commissions ont ete calculees dessus. Faire echouer `charger` serait faux deux"
                " fois, puisque cette tache a reussi et que son echec priverait les lots sains de la"
                " suite de la chaine. Mais un graphe entierement vert quand neuf bordereaux sur"
                " vingt-sept ont ete refuses ne previent personne, alors qu'un bordereau refuse"
                " demande un appel a la compagnie.\n\n"
                "La tache est donc terminale et dediee : tout le reste a deja tourne, le graphe"
                " devient rouge, l'alerte part, et rien n'a ete empeche. La fenetre examinee couvre les"
                " vingt-quatre dernieres heures, lues sur l'horloge de la base, pour qu'un lot rejete"
                " avant-hier et corrige depuis ne fasse pas rougir le graphe d'aujourd'hui."
            ),
        )
        rapport >> journal >> alerter

    fin = EmptyOperator(task_id="fin")

    debut >> ingestion >> transformer >> calculs >> publier >> documenter >> comptes_rendus >> fin
