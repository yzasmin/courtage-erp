"""Tests du generateur : reproductibilite a graine egale, et presence des signaux realistes.

Critere d'acceptation du module 1 : « generation reproductible, meme graine, memes donnees ». La preuve
publiee est produite par `scripts/preuve_reproductibilite.py` sur le jeu complet ; ces tests font la
meme verification sur un volume reduit, pour qu'une regression soit detectee par la suite ordinaire et
non seulement par le script de preuve.

Ils verifient aussi que les trois signaux exiges par la specification sont bien dans les donnees :
saisonnalite des prestations, hausses tarifaires au 1er janvier, et resiliations avec des causes.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from random import Random

import pytest
from sqlalchemy import extract, func, select, text
from sqlalchemy.orm import Session

from courtage.config import RACINE_PROJET
from courtage.db import cree_moteur
from courtage.generateur import genere_tout
from courtage.generateur.empreinte import empreinte_complete
from courtage.generateur.outils import age_a_la_date, ajoute_mois, dernier_jour_du_mois, tire_pondere
from courtage.generateur.parametres import POIDS_SAISON_PRESTATIONS, REVALORISATION_BP_PAR_ANNEE
from courtage.modeles.enums import StatutContrat, TypeAvenant
from courtage.modeles.financier import AppelCotisation, Prestation
from courtage.modeles.portefeuille import Adherent, Avenant, Contrat

#: Volume reduit : la generation complete met une dizaine de secondes, ce qui serait trop pour la suite.
GRAINE_A = 7
GRAINE_B = 8
DATE_REFERENCE = date(2026, 9, 30)


@pytest.fixture(scope="module")
def jeu_reduit(tmp_path_factory):
    """Genere deux fois le meme petit jeu, et une fois un jeu de graine differente.

    Le volume est reduit en abaissant les parametres de volumetrie du module le temps de la generation,
    puis en les remettant : les autres tests doivent retrouver les valeurs du projet.
    """
    from courtage.generateur import parametres as reglages

    dossier = tmp_path_factory.mktemp("generation")
    originaux = (reglages.NB_ENTREPRISES, reglages.NB_ADHERENTS_INDIVIDUELS,
                 reglages.NB_ADHERENTS_COLLECTIFS_MIN, reglages.NB_ADHERENTS_COLLECTIFS_MAX)
    reglages.NB_ENTREPRISES = 3
    reglages.NB_ADHERENTS_INDIVIDUELS = 120
    reglages.NB_ADHERENTS_COLLECTIFS_MIN = 4
    reglages.NB_ADHERENTS_COLLECTIFS_MAX = 9

    resultats = {}
    try:
        for nom, graine in (("a1", GRAINE_A), ("a2", GRAINE_A), ("b", GRAINE_B)):
            fichier = dossier / f"{nom}.db"
            url = f"sqlite+pysqlite:///{fichier.as_posix()}"
            moteur = cree_moteur(url=url, echo=False)
            # Schema pose directement ici, et non par Alembic : ces trois bases jetables servent a
            # comparer des empreintes, et les migrations sont deja eprouvees par la fixture `moteur`
            # et par le script de preuve.
            from courtage.modeles import Base

            Base.metadata.create_all(moteur)
            with Session(moteur) as session:
                compte_rendu = genere_tout(session, graine=graine, date_reference=DATE_REFERENCE)
                session.commit()
                resultats[nom] = {
                    "empreinte": empreinte_complete(session),
                    "compte_rendu": compte_rendu.en_dictionnaire(),
                }
            moteur.dispose()
    finally:
        (reglages.NB_ENTREPRISES, reglages.NB_ADHERENTS_INDIVIDUELS,
         reglages.NB_ADHERENTS_COLLECTIFS_MIN, reglages.NB_ADHERENTS_COLLECTIFS_MAX) = originaux

    return resultats


# --- Reproductibilite -----------------------------------------------------------------------------


def test_deux_executions_de_meme_graine_donnent_la_meme_empreinte(jeu_reduit) -> None:
    assert jeu_reduit["a1"]["empreinte"]["sha256_global"] == jeu_reduit["a2"]["empreinte"]["sha256_global"]


def test_la_reproductibilite_vaut_table_par_table(jeu_reduit) -> None:
    """L'empreinte globale pourrait coincider par accident ; table par table, c'est exclu."""
    tables_a = jeu_reduit["a1"]["empreinte"]["tables"]
    tables_b = jeu_reduit["a2"]["empreinte"]["tables"]
    assert sorted(tables_a) == sorted(tables_b)
    for nom in sorted(tables_a):
        assert tables_a[nom] == tables_b[nom], f"la table {nom} differe entre deux executions"


def test_la_volumetrie_est_identique_a_graine_egale(jeu_reduit) -> None:
    assert jeu_reduit["a1"]["compte_rendu"] == jeu_reduit["a2"]["compte_rendu"]


def test_une_graine_differente_donne_un_jeu_different(jeu_reduit) -> None:
    """Sinon la graine ne servirait a rien, et la reproductibilite serait triviale."""
    assert jeu_reduit["a1"]["empreinte"]["sha256_global"] != jeu_reduit["b"]["empreinte"]["sha256_global"]


def test_l_empreinte_couvre_un_volume_non_nul(jeu_reduit) -> None:
    assert jeu_reduit["a1"]["empreinte"]["total_lignes"] > 1_000


def test_le_tirage_pondere_est_deterministe() -> None:
    """Les cles sont triees avant le tirage : sans cela, l'ordre d'iteration d'un ensemble de chaines
    varierait d'un processus a l'autre et la generation ne serait pas reproductible."""
    poids = {"mensuel": 62, "trimestriel": 24, "semestriel": 9, "annuel": 5}
    premier = [tire_pondere(Random(1), poids) for _ in range(50)]
    second = [tire_pondere(Random(1), poids) for _ in range(50)]
    assert premier == second


# --- Outils de date --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("depart", "mois", "attendu"),
    [
        (date(2024, 1, 31), 1, date(2024, 2, 29)),  # annee bissextile
        (date(2025, 1, 31), 1, date(2025, 2, 28)),
        (date(2025, 1, 15), 12, date(2026, 1, 15)),
        (date(2025, 12, 1), 1, date(2026, 1, 1)),
        (date(2025, 3, 31), 1, date(2025, 4, 30)),
    ],
)
def test_le_decalage_de_mois_replie_sur_la_fin_du_mois(depart: date, mois: int, attendu: date) -> None:
    """Sans ce repli, la generation planterait sur les contrats a echeance un 31."""
    assert ajoute_mois(depart, mois) == attendu


@pytest.mark.parametrize(
    ("jour", "attendu"),
    [
        (date(2024, 2, 10), date(2024, 2, 29)),
        (date(2025, 2, 10), date(2025, 2, 28)),
        (date(2025, 12, 1), date(2025, 12, 31)),
    ],
)
def test_dernier_jour_du_mois(jour: date, attendu: date) -> None:
    assert dernier_jour_du_mois(jour) == attendu


def test_age_revolu() -> None:
    naissance = date(1990, 6, 15)
    assert age_a_la_date(naissance, date(2025, 6, 14)) == 34
    assert age_a_la_date(naissance, date(2025, 6, 15)) == 35


# --- Signaux realistes, verifies sur la base de demonstration ------------------------------------
# Ces tests lisent la base du test, qui ne contient que le referentiel : ils sont alors sans objet et
# se declarent sautes. Lances contre la base de demonstration, ils verifient les trois signaux.


def _base_de_demonstration_presente(session: Session) -> bool:
    return (session.scalar(select(func.count(Contrat.id))) or 0) > 1_000


def test_les_revalorisations_tombent_au_1er_janvier(session) -> None:
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    dates = session.scalars(
        select(Avenant.date_effet)
        .where(Avenant.type_avenant == TypeAvenant.REVALORISATION_TARIFAIRE)
        .limit(2_000)
    )
    for jour in dates:
        assert (jour.month, jour.day) == (1, 1)


def test_les_annees_de_revalorisation_sont_celles_prevues(session) -> None:
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    # `extract` et non `strftime` : `strftime` n'existe que sur SQLite, et ce test doit aussi passer
    # sur la base PostgreSQL du compose. Le defaut ne se voyait pas tant que la suite ne tournait que
    # sur SQLite.
    annees = set(
        session.scalars(
            select(extract("year", Avenant.date_effet))
            .where(Avenant.type_avenant == TypeAvenant.REVALORISATION_TARIFAIRE)
            .distinct()
        )
    )
    assert {int(a) for a in annees} <= set(REVALORISATION_BP_PAR_ANNEE)


def test_les_prestations_suivent_la_saisonnalite(session) -> None:
    """Creux en juillet et aout, pic de novembre a janvier : c'est ce que la courbe du module de
    pilotage doit faire apparaitre."""
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    par_mois = Counter(
        int(mois) for mois in session.scalars(select(extract("month", Prestation.date_soins)))
    )
    creux = min(par_mois[7], par_mois[8])
    pic = max(par_mois[11], par_mois[12], par_mois[1])
    assert pic > creux, f"aucune saisonnalite visible : {dict(sorted(par_mois.items()))}"
    # Le mois le plus creux doit etre juillet ou aout, comme les poids le prevoient.
    mois_le_plus_creux = min(par_mois, key=lambda m: par_mois[m])
    assert mois_le_plus_creux in (7, 8)


@pytest.mark.parametrize("annee", [2024, 2025])
def test_le_ratio_sinistres_sur_primes_est_plausible_dans_chaque_branche(session, annee) -> None:
    """Les prestations suivent la cotisation : sante individuelle et collective, 65 a 90 pour cent.

    Avant le calibrage des demandes sur la cotisation du contrat, le ratio depassait 150 pour cent. Cette
    mesure est une approximation (cotisations emises dans l'annee, hors taxe, au lieu d'acquises), assez
    proche pour garder la fourchette ; le ratio publie, sur les acquises, est celui de `docs/kpi.md`.
    La prevoyance est absente : le cabinet n'y regle aucune prestation.
    """
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    debut, fin = date(annee, 1, 1), date(annee + 1, 1, 1)
    prestations = dict(
        session.execute(
            text(
                "select b.code, sum(pr.montant_rembourse_cents) from prestation pr"
                " join contrat c on c.id = pr.contrat_id join produit p on p.id = c.produit_id"
                " join branche b on b.id = p.branche_id"
                " where pr.statut = 'reglee' and pr.date_reglement >= :debut and pr.date_reglement < :fin"
                " group by b.code"
            ),
            {"debut": debut, "fin": fin},
        ).all()
    )
    cotisations = dict(
        session.execute(
            text(
                "select b.code, sum(a.montant_ht_cents) from appel_cotisation a"
                " left join contrat c on c.id = a.contrat_id"
                " left join police_collective pc on pc.id = a.police_id"
                " join produit p on p.id = coalesce(c.produit_id, pc.produit_id)"
                " join branche b on b.id = p.branche_id"
                " where a.date_echeance >= :debut and a.date_echeance < :fin group by b.code"
            ),
            {"debut": debut, "fin": fin},
        ).all()
    )
    assert "PV" not in prestations, "aucune prestation de prevoyance : l'acte n'est pas delegue"
    for branche in ("SI", "SC"):
        ratio = prestations[branche] / cotisations[branche]
        assert 0.65 <= ratio <= 0.90, f"{branche} {annee} : ratio {ratio:.2f} hors de la fourchette"


def test_la_consommation_est_dispersee_et_non_uniforme(session) -> None:
    """Beaucoup de contrats consomment peu, une minorite beaucoup : un ratio uniforme serait aussi faux
    qu'un ratio demesure. Les 10 pour cent de contrats les plus consommateurs portent au moins le tiers
    des remboursements, et une part notable des contrats n'a aucune prestation reglee."""
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    totaux = sorted(
        (
            ligne[0] or 0
            for ligne in session.execute(
                text(
                    "select (select sum(pr.montant_rembourse_cents) from prestation pr"
                    " where pr.contrat_id = c.id and pr.statut = 'reglee') from contrat c"
                    " join produit p on p.id = c.produit_id join branche b on b.id = p.branche_id"
                    " where b.code in ('SI', 'SC') and c.statut <> 'devis'"
                )
            )
        ),
        reverse=True,
    )
    dixieme = max(1, len(totaux) // 10)
    assert sum(totaux[:dixieme]) >= sum(totaux) / 3
    assert sum(1 for total in totaux if total == 0) / len(totaux) >= 0.03


def test_les_poids_de_saison_couvrent_les_douze_mois() -> None:
    assert len(POIDS_SAISON_PRESTATIONS) == 12
    assert min(POIDS_SAISON_PRESTATIONS) > 0


def test_les_resiliations_portent_toutes_un_motif(session) -> None:
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    sans_motif = session.scalar(
        select(func.count(Contrat.id)).where(
            Contrat.statut == StatutContrat.RESILIE, Contrat.motif_resiliation.is_(None)
        )
    )
    assert sans_motif == 0


def test_aucun_devis_n_est_quittance(session) -> None:
    """Un devis n'a pas pris effet : l'appeler en cotisation serait une erreur de gestion."""
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    quittances = session.scalar(
        select(func.count(AppelCotisation.id))
        .join(Contrat, Contrat.id == AppelCotisation.contrat_id)
        .where(Contrat.statut == StatutContrat.DEVIS)
    )
    assert quittances == 0


def test_la_volumetrie_de_demonstration_respecte_la_specification(session) -> None:
    """Environ 5 000 adherents, 40 entreprises, 10 apporteurs, 3 compagnies, 8 produits."""
    if not _base_de_demonstration_presente(session):
        pytest.skip("base de test sans portefeuille genere")
    from courtage.modeles.referentiel import Apporteur, Compagnie, Produit

    assert 4_500 <= (session.scalar(select(func.count(Adherent.id))) or 0) <= 5_800
    assert session.scalar(select(func.count(Compagnie.id))) == 3
    assert session.scalar(select(func.count(Produit.id))) == 8
    assert session.scalar(select(func.count(Apporteur.id))) == 10


def test_le_dossier_temporaire_des_tests_est_bien_hors_du_depot() -> None:
    """Garde-fou : par defaut, un test ne doit pas ecrire dans le depot.

    Sans objet quand `COURTAGE_BASE_URL` est fournie : la suite est alors lancee volontairement contre
    une base choisie, par exemple celle de demonstration, pour produire les preuves du module.
    """
    import os

    if os.environ.get("COURTAGE_BASE_TESTS_FOURNIE") == "1":
        pytest.skip("base fournie explicitement, le garde-fou ne s'applique pas")

    from courtage.config import parametres

    chemin = parametres.base_url.removeprefix("sqlite+pysqlite:///")
    assert Path(tempfile.gettempdir()) in Path(chemin).parents


# --- Independance a l'horloge -------------------------------------------------------------------


def _empreinte_dans_un_sous_processus(dossier: Path, graine: int, annee_simulee: int) -> str:
    """Genere un jeu reduit dans un processus neuf, avec une horloge et un grain de hachage imposes.

    Deux precautions, pour que le test prouve vraiment ce qu'il annonce :

    - **un sous-processus**, parce qu'une horloge simulee dans le processus courant n'atteindrait pas
      le code deja importe de la meme facon, et parce que deux executions dans le meme processus
      partagent le grain de hachage des chaines ;
    - **un `PYTHONHASHSEED` different a chaque appel**, pour attraper toute dependance a l'ordre
      d'iteration d'un ensemble de chaines, qui varie d'un processus a l'autre.
    """
    programme = f'''
import datetime as _dt


class _DateFigee(_dt.date):
    @classmethod
    def today(cls):
        return cls({annee_simulee}, 6, 15)


_dt.date = _DateFigee

from datetime import date
from random import Random

from sqlalchemy.orm import Session

from courtage.config import RACINE_PROJET
from courtage.db import cree_moteur
from courtage.generateur import genere_tout, parametres as reglages
from courtage.generateur.empreinte import empreinte_complete
from courtage.modeles import Base

reglages.NB_ENTREPRISES = 2
reglages.NB_ADHERENTS_INDIVIDUELS = 60
reglages.NB_ADHERENTS_COLLECTIFS_MIN = 3
reglages.NB_ADHERENTS_COLLECTIFS_MAX = 6

moteur = cree_moteur(url=r"sqlite+pysqlite:///{(dossier / f"horloge_{annee_simulee}.db").as_posix()}", echo=False)
Base.metadata.create_all(moteur)
with Session(moteur) as session:
    genere_tout(session, graine={graine}, date_reference=date(2026, 9, 30))
    session.commit()
    print(empreinte_complete(session)["sha256_global"])
'''
    environnement = dict(os.environ)
    environnement["PYTHONHASHSEED"] = str(annee_simulee)
    environnement["COURTAGE_BASE_URL"] = "sqlite+pysqlite:///:memory:"
    resultat = subprocess.run(
        [sys.executable, "-c", programme],
        capture_output=True,
        text=True,
        env=environnement,
        cwd=str(RACINE_PROJET),
        check=False,
    )
    if resultat.returncode != 0:
        raise AssertionError(f"la generation a echoue :\n{resultat.stderr[-2000:]}")
    return resultat.stdout.strip().splitlines()[-1]


def test_la_generation_ne_depend_ni_de_l_annee_en_cours_ni_du_grain_de_hachage(tmp_path) -> None:
    """Meme graine, meme date de reference, deux annees et deux grains de hachage : meme empreinte.

    C'est le test qui manquait, et son absence rendait fausse l'affirmation la plus mise en avant du
    projet. L'age des adherents etait calcule avec `date.today()` : la meme graine aurait produit des
    ages differents au 1er janvier suivant, donc d'autres cotisations, d'autres probabilites de
    resiliation, et une autre empreinte. Les deux executions comparees par la preuve de
    reproductibilite ayant toujours lieu le meme jour, rien ne l'aurait signale.
    """
    en_2026 = _empreinte_dans_un_sous_processus(tmp_path, GRAINE_A, 2026)
    en_2031 = _empreinte_dans_un_sous_processus(tmp_path, GRAINE_A, 2031)
    assert en_2026 == en_2031, (
        "l'empreinte depend de l'annee en cours ou du grain de hachage :"
        f" {en_2026} en 2026 contre {en_2031} en 2031"
    )
