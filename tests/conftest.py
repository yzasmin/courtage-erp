"""Fixtures des tests.

Trois partis pris, qui expliquent la structure.

**Les tests montent le schema par Alembic, pas par `create_all`.** C'est plus lent de quelques secondes,
et cela teste la chose qui sera reellement executee en production. Un schema cree par `create_all` peut
differer de celui que les migrations produisent, et la difference ne se decouvre alors qu'au deploiement.

**Le jeu de donnees des tests est minuscule et construit a la main.** Le generateur complet met une
dizaine de secondes : le lancer a chaque test rendrait la suite inutilisable. Les tests de
reproductibilite, eux, appellent bien le vrai generateur, sur un petit volume.

**Chaque test travaille dans une transaction annulee a la fin.** Les tests restent donc independants, et
l'ordre dans lequel ils s'executent n'a aucune influence.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

# L'adresse de la base doit etre fixee avant que `courtage.config` ne soit importe par autre chose.
#
# Par defaut, la suite travaille sur une base temporaire jetable : les tests sont alors independants de
# l'etat du poste. Mais si `COURTAGE_BASE_URL` est deja fournie, elle est respectee, ce qui permet de
# lancer la meme suite **contre la base de demonstration**. Les tests de signaux realistes, qui se
# declarent sautes faute de portefeuille, s'executent alors reellement. C'est ainsi que les preuves du
# module 1 sont produites, sur SQLite comme sur PostgreSQL.
_BASE_FOURNIE = os.environ.get("COURTAGE_BASE_URL")
os.environ["COURTAGE_BASE_TESTS_FOURNIE"] = "1" if _BASE_FOURNIE else "0"
if _BASE_FOURNIE:
    _FICHIER_BASE = None
else:
    _DOSSIER_TEMPORAIRE = tempfile.mkdtemp(prefix="courtage-tests-")
    _FICHIER_BASE = Path(_DOSSIER_TEMPORAIRE) / "tests.db"
    os.environ["COURTAGE_BASE_URL"] = f"sqlite+pysqlite:///{_FICHIER_BASE.as_posix()}"

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from courtage.config import RACINE_PROJET
from courtage.db import cree_moteur
from courtage.generateur.referentiel import genere_referentiel
from courtage.modeles.enums import Fractionnement
from courtage.services.contrats import DemandeSouscription, souscrit_contrat

#: Graine des tests, distincte de celle du projet : une suite qui passerait seulement avec la graine de
#: production cacherait une dependance a des valeurs particulieres.
GRAINE_TESTS = 4242

#: Dates de reference du jeu de test. Fixees, pour que les tests ne changent pas de resultat demain.
DATE_SOUSCRIPTION = date(2024, 2, 10)
DATE_EFFET = date(2024, 3, 1)
DATE_REFERENCE = date(2026, 9, 30)


def _config_alembic() -> Config:
    config = Config(str(RACINE_PROJET / "alembic.ini"))
    config.set_main_option("script_location", str(RACINE_PROJET / "migrations"))
    return config


def _corrige_les_transactions_sqlite(moteur_test) -> None:
    """Rend les points de reprise utilisables sur SQLite, ce qui est la condition de l'isolation des tests.

    Le probleme, et il coute du temps a qui ne le connait pas. Le pilote `pysqlite` ouvre et valide les
    transactions tout seul, a sa facon, en devinant d'apres le type de requete. Resultat : un
    `SAVEPOINT` pose par SQLAlchemy n'est pas dans la transaction que l'on croit, et un `COMMIT` emis par
    le code teste valide **la transaction englobante** au lieu de relacher seulement le point de reprise.
    L'annulation de fin de test ne ramene alors rien, et les donnees d'un test fuient dans le suivant.
    Le symptome observe est une violation d'unicite dans un test qui n'a rien fait de faux.

    Le correctif est celui que documente SQLAlchemy pour ce pilote : on desactive la gestion implicite du
    pilote, puis on emet soi-meme le `BEGIN`. C'est applique au moteur **de test** seulement, pour ne
    rien changer au comportement du code livre.
    """
    from sqlalchemy import event

    @event.listens_for(moteur_test, "connect")
    def _desactive_la_gestion_implicite(connexion_dbapi, _enregistrement):
        connexion_dbapi.isolation_level = None

    @event.listens_for(moteur_test, "begin")
    def _ouvre_la_transaction(connexion):
        connexion.exec_driver_sql("BEGIN")


@pytest.fixture(scope="session")
def moteur():
    """Moteur sur une base temporaire, schema monte par les migrations."""
    moteur_test = cree_moteur(echo=False)
    if moteur_test.dialect.name == "sqlite":
        _corrige_les_transactions_sqlite(moteur_test)
    command.upgrade(_config_alembic(), "head")
    yield moteur_test
    moteur_test.dispose()


@pytest.fixture(scope="session")
def referentiel_pose(moteur):
    """Pose le referentiel une seule fois : branches, produits, formules, apporteurs, taux, conventions.

    Idempotente : quand la base en contient deja un, par exemple celle de demonstration, la fixture ne
    reecrit rien et se contente de lire les codes. Sans cela, lancer la suite contre la base de
    demonstration echouerait sur l'unicite des codes de produit.
    """
    from random import Random

    from sqlalchemy import func, select

    from courtage.modeles.referentiel import Branche

    with Session(moteur) as session:
        if (session.scalar(select(func.count(Branche.id))) or 0) == 0:
            genere_referentiel(session, Random(GRAINE_TESTS), DATE_REFERENCE)
            session.commit()

        from courtage.modeles.referentiel import Apporteur, Formule, Produit

        return {
            "produits": sorted(session.scalars(select(Produit.code))),
            "apporteurs": sorted(session.scalars(select(Apporteur.code))),
            "formules": sorted(set(session.scalars(select(Formule.code)))),
        }


@pytest.fixture
def session(moteur, referentiel_pose):
    """Session de test, dans une transaction annulee a la fin du test."""
    connexion = moteur.connect()
    transaction = connexion.begin()
    session_test = Session(bind=connexion, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session_test
    finally:
        session_test.close()
        transaction.rollback()
        connexion.close()


@pytest.fixture
def adherent(session):
    """Un adherent individuel, cree a la demande du test."""
    from courtage.modeles.portefeuille import Adherent

    personne = Adherent(
        numero_adherent="A999001",
        nom="Teissier",
        prenom="Camille",
        date_naissance=date(1982, 5, 14),
        sexe="F",
        code_postal="34070",
        departement="34",
        courriel="camille.teissier@exemple.invalid",
        telephone="0612345678",
        entreprise_id=None,
        date_creation=DATE_SOUSCRIPTION,
    )
    session.add(personne)
    session.flush()
    return personne


@pytest.fixture
def contrat_oceane(session, adherent):
    """Un devis sur un produit Oceane, dont la compagnie delegue tous les actes de gestion.

    C'est le contrat de reference des tests de cycle de vie : rien n'y est bloque par la delegation, donc
    un refus observe vient bien de la regle testee.
    """
    return souscrit_contrat(
        session,
        DemandeSouscription(
            numero_adherent=adherent.numero_adherent,
            code_produit="SI-ESSENTIEL",
            code_formule="F2",
            code_apporteur="AP01",
            date_souscription=DATE_SOUSCRIPTION,
            cotisation_mensuelle_cents=6_840,
            fractionnement=Fractionnement.MENSUEL,
        ),
    )


@pytest.fixture
def contrat_prevoyance(session, adherent):
    """Un devis sur un produit Littoral, dont la compagnie ne delegue pas la gestion des prestations."""
    return souscrit_contrat(
        session,
        DemandeSouscription(
            numero_adherent=adherent.numero_adherent,
            code_produit="PV-DECES",
            code_formule="F1",
            code_apporteur="AP03",
            date_souscription=DATE_SOUSCRIPTION,
            cotisation_mensuelle_cents=2_400,
            fractionnement=Fractionnement.TRIMESTRIEL,
        ),
    )


@pytest.fixture
def client(session):
    """Client de test de l'API, branche sur la session du test.

    La dependance de session est remplacee pour que les ecritures faites par l'API soient visibles du
    test, et annulees avec lui.
    """
    from starlette.testclient import TestClient

    from courtage.api.app import application
    from courtage.db import session_api

    def session_de_test():
        yield session

    application.dependency_overrides[session_api] = session_de_test
    with TestClient(application) as client_test:
        yield client_test
    application.dependency_overrides.clear()
