"""Fixtures des tests du module 2, isolees de celles du module 1.

Les fixtures du module 1 restent disponibles ici, pytest heritant des `conftest.py` parents. Ce fichier
n'ajoute que ce dont la chaine des flux a besoin et que le module 1 n'a pas : un espace de travail de
flux dans un dossier temporaire, un petit portefeuille avec des appels de cotisation, et des raccourcis
pour deposer un fichier de bordereau.

Un parti pris, qui explique la taille des jeux de donnees ici. Les tests de la chaine ne rejouent pas le
generateur complet : ils construisent trois ou quatre appels a la main. Un test qui met douze secondes a
preparer ses donnees n'est pas relance assez souvent pour servir a quelque chose, et surtout un echec
sur un jeu de cinquante mille lignes ne dit pas quelle ligne a pose probleme.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from courtage.modeles.enums import AssietteCommission, MoyenPaiement, StatutAppel, StatutRapprochement
from courtage.modeles.financier import AppelCotisation, Encaissement
from courtage.modeles.referentiel import TauxCommission, TauxRetrocession
from courtage.services.contrats import met_en_vigueur

#: Mois couvert par les fichiers des tests.
PERIODE_TEST = date(2026, 6, 1)
#: Echeance des appels construits par les fixtures.
ECHEANCE_TEST = date(2026, 6, 1)
#: Date d'effet donnee au contrat de reference, bien avant les periodes testees.
DATE_EFFET_TEST = date(2024, 3, 1)


@pytest.fixture
def espace_flux(tmp_path, monkeypatch):
    """Espace de travail des flux dans un dossier temporaire, remis a zero a chaque test.

    `racine_flux()` relit l'environnement a chaque appel, ce qui permet de la detourner ici sans
    recharger le module des parametres.
    """
    racine = tmp_path / "flux"
    (racine / "arrivee").mkdir(parents=True)
    monkeypatch.setenv("COURTAGE_FLUX_RACINE", str(racine))
    return racine


@pytest.fixture
def contrat_en_vigueur(session, contrat_oceane):
    """Met le contrat de reference en vigueur avant la periode des tests.

    Le contrat des fixtures du module 1 est un devis, et un devis n'a pas de date d'effet. Tout flux
    rattache a un devis est donc, a juste titre, declare incoherent par le controle de periode : il n'y
    a aucune garantie a quittancer. Les tests de la chaine ont besoin d'un contrat reellement en cours,
    et le mettre en vigueur ici est aussi une verification utile du chemin d'ecriture du module 1.
    """
    met_en_vigueur(session, contrat_oceane, date_effet=DATE_EFFET_TEST)
    session.flush()
    return contrat_oceane


@pytest.fixture
def appels_oceane(session, contrat_en_vigueur):
    """Trois appels de cotisation mensuels sur le contrat de reference, dont le dernier en juin 2026.

    Trois et non un : le controle du montant atypique exige un historique minimal, et le rapprochement
    par montant et date doit pouvoir choisir entre plusieurs echeances du meme contrat.
    """
    appels = []
    for rang in range(3):
        debut = date(2026, 4 + rang, 1)
        fin = (date(2026, 5 + rang, 1) if rang < 2 else date(2026, 7, 1)) - timedelta(days=1)
        appel = AppelCotisation(
            reference_appel=f"APP-TEST-{debut:%Y%m}",
            contrat_id=contrat_en_vigueur.id,
            police_id=None,
            nombre_affilies=1,
            periode_debut=debut,
            periode_fin=fin,
            date_echeance=debut,
            montant_ht_cents=6_840,
            montant_taxe_cents=908,
            montant_total_cents=7_748,
            taux_taxe_bp=1_327,
            statut=StatutAppel.ATTENDU,
        )
        session.add(appel)
        appels.append(appel)
    session.flush()
    return appels


@pytest.fixture
def encaissement_oceane(session, contrat_oceane, appels_oceane):
    """Un mouvement bancaire deja connu du coeur ERP, rattache au dernier appel."""
    mouvement = Encaissement(
        reference_bancaire="ENC-TEST-0000001",
        appel_id=None,
        contrat_id=contrat_oceane.id,
        date_encaissement=ECHEANCE_TEST + timedelta(days=4),
        montant_cents=7_748,
        moyen=MoyenPaiement.VIREMENT,
        statut_rapprochement=StatutRapprochement.NON_RAPPROCHE,
        libelle_releve="COTIS TEST 06/2026",
    )
    session.add(mouvement)
    session.flush()
    return mouvement


@pytest.fixture
def taux_du_produit(session, contrat_oceane):
    """Deux baremes de commission successifs sur le produit du contrat, et un taux de retrocession.

    Deux baremes, parce que c'est la seule facon de verifier que le calcul retient celui en vigueur **a
    la date d'echeance** et non le plus recent. Un seul bareme rendrait le test incapable de distinguer
    les deux comportements.
    """
    produit_id = contrat_oceane.produit_id
    anciens = list(
        session.scalars(select(TauxCommission).where(TauxCommission.produit_id == produit_id))
    )
    for ancien in anciens:
        session.delete(ancien)
    session.flush()

    ancien_bareme = TauxCommission(
        produit_id=produit_id,
        taux_bp=1_000,
        assiette=AssietteCommission.COTISATION_ENCAISSEE,
        date_debut_validite=date(2024, 1, 1),
        date_fin_validite=date(2026, 5, 31),
    )
    nouveau_bareme = TauxCommission(
        produit_id=produit_id,
        taux_bp=1_500,
        assiette=AssietteCommission.COTISATION_ENCAISSEE,
        date_debut_validite=date(2026, 6, 1),
        date_fin_validite=None,
    )
    session.add_all([ancien_bareme, nouveau_bareme])

    retrocessions = list(
        session.scalars(
            select(TauxRetrocession).where(TauxRetrocession.apporteur_id == contrat_oceane.apporteur_id)
        )
    )
    for ligne in retrocessions:
        session.delete(ligne)
    session.flush()
    session.add(
        TauxRetrocession(
            apporteur_id=contrat_oceane.apporteur_id,
            produit_id=None,
            taux_bp=6_000,
            date_debut_validite=date(2024, 1, 1),
            date_fin_validite=None,
        )
    )
    session.flush()
    return {"ancien_bp": 1_000, "nouveau_bp": 1_500, "retrocession_bp": 6_000}
