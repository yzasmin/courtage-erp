"""Graphe mensuel de scoring du risque de resiliation (module 5).

Le 1er de chaque mois, deux taches :

1. `variables`  `dbt build` du modele `ml_variables_resiliation` et de ses tests, dont celui qui verifie
                qu'aucune variable ne lit d'information posterieure a la date d'observation. Un test en
                echec arrete le graphe : on ne score pas sur des variables douteuses.
2. `scorer`     `courtage ml scorer` : probabilite, decile et trois principaux facteurs de chaque contrat
                au portefeuille, ecrits dans la table `score_resiliation` que lit la fiche adherent.

Le reapprentissage n'est pas mensuel. Il se fait a la main, une fois par an apres l'echeance du 1er
janvier, avec `courtage ml entrainer`, qui remesure le modele sur l'annee la plus recente entierement
observee avant de remplacer le fichier du modele. Un modele qui change chaque mois sans etre remesure
serait un modele que personne ne controle.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

COURTAGE = os.environ.get("COURTAGE_EXECUTABLE", "/opt/courtage-venv/bin/courtage")
DBT = os.environ.get("DBT_EXECUTABLE", "/opt/dbt-venv/bin/dbt")
PROJET_DBT = os.environ.get("DBT_PROJET", "/opt/courtage/dbt")
DBT_COMMUN = f"--project-dir {PROJET_DBT} --profiles-dir {PROJET_DBT} --no-use-colors"

REGLAGES_PAR_DEFAUT = {
    "owner": "cabinet-grossiste",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
    "depends_on_past": False,
    "email_on_failure": False,
}

with DAG(
    dag_id="courtage_scoring_resiliation",
    description="Score mensuel du risque de resiliation de chaque contrat, avec ses trois principaux facteurs",
    doc_md=__doc__,
    default_args=REGLAGES_PAR_DEFAUT,
    schedule="0 4 1 * *",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    tags=["courtage", "resiliation", "module-5"],
) as graphe:
    variables = BashOperator(
        task_id="variables",
        bash_command=f"{DBT} build --select ml_variables_resiliation {DBT_COMMUN}",
        doc_md="Variables a la date d'observation et test d'absence d'information posterieure.",
    )
    scorer = BashOperator(
        task_id="scorer",
        bash_command=f"{COURTAGE} ml scorer",
        doc_md="Probabilite, decile et trois facteurs par contrat, dans la table `score_resiliation`.",
    )

    variables >> scorer
