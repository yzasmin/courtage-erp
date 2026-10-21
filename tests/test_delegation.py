"""Tests de la delegation de gestion : le code refuse-t-il un acte non delegue.

C'est la regle qui distingue un ERP de courtier delegataire d'un simple logiciel de portefeuille. Les
cas couverts :

- un acte delegue passe ;
- un acte non delegue est refuse, avec un message qui cite le perimetre reel ;
- un produit sans convention en vigueur ne permet aucun acte, plutot que de tout permettre ;
- une convention expiree ne permet plus rien ;
- la portee declaree « totale » n'autorise rien par elle-meme, seule la liste des actes compte ;
- deux conventions qui se chevauchent sont refusees au lieu d'etre arbitrees au hasard.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from courtage.domaine.delegation import (
    ActeNonDelegue,
    DelegationAmbigue,
    perimetre_delegue,
    verifie_acte_delegue,
)
from courtage.modeles.delegation import ActeDelegue, ConventionDelegation, ConventionProduit
from courtage.modeles.enums import ActeGestion, Fractionnement, PorteeDelegation
from courtage.modeles.referentiel import Produit
from courtage.services import contrats as service

JOUR = date(2025, 6, 15)


def _produit(session, code: str) -> Produit:
    return session.scalars(select(Produit).where(Produit.code == code)).one()


# --- Le perimetre, tel que le referentiel genere le pose ---------------------------------------


def test_oceane_delegue_tous_les_actes_sauf_les_sinistres(session) -> None:
    perimetre = perimetre_delegue(session, _produit(session, "SI-ESSENTIEL").id, JOUR)
    assert perimetre.portee_declaree == PorteeDelegation.TOTALE.value
    assert perimetre.autorise(ActeGestion.AFFILIATION)
    assert perimetre.autorise(ActeGestion.QUITTANCEMENT)
    assert perimetre.autorise(ActeGestion.ENCAISSEMENT)
    assert perimetre.autorise(ActeGestion.GESTION_PRESTATIONS)


def test_pyrene_ne_delegue_pas_l_encaissement(session) -> None:
    """La compagnie preleve elle-meme les cotisations : le cabinet quittance mais n'encaisse pas."""
    perimetre = perimetre_delegue(session, _produit(session, "SI-EQUILIBRE").id, JOUR)
    assert perimetre.autorise(ActeGestion.QUITTANCEMENT)
    assert not perimetre.autorise(ActeGestion.ENCAISSEMENT)


def test_littoral_ne_delegue_pas_les_prestations(session) -> None:
    """Un sinistre de prevoyance suppose une expertise medicale, que l'assureur garde."""
    perimetre = perimetre_delegue(session, _produit(session, "PV-DECES").id, JOUR)
    assert perimetre.autorise(ActeGestion.ENCAISSEMENT)
    assert not perimetre.autorise(ActeGestion.GESTION_PRESTATIONS)
    assert not perimetre.autorise(ActeGestion.GESTION_SINISTRES)


# --- Le refus ------------------------------------------------------------------------------------


def test_un_acte_delegue_passe(session) -> None:
    verifie_acte_delegue(session, _produit(session, "SI-ESSENTIEL").id, ActeGestion.AFFILIATION, JOUR)


def test_un_acte_non_delegue_est_refuse(session) -> None:
    produit = _produit(session, "PV-DECES")
    with pytest.raises(ActeNonDelegue) as refus:
        verifie_acte_delegue(session, produit.id, ActeGestion.GESTION_PRESTATIONS, JOUR)
    assert refus.value.acte is ActeGestion.GESTION_PRESTATIONS
    assert refus.value.produit_id == produit.id


def test_le_refus_cite_le_perimetre_reellement_delegue(session) -> None:
    """Un gestionnaire doit comprendre le refus sans ouvrir la convention papier."""
    produit = _produit(session, "SI-EQUILIBRE")
    with pytest.raises(ActeNonDelegue) as refus:
        verifie_acte_delegue(session, produit.id, ActeGestion.ENCAISSEMENT, JOUR)
    message = str(refus.value)
    assert "CONV-PYR-2020" in message
    assert "quittancement" in message


def test_un_produit_sans_convention_ne_permet_aucun_acte(session) -> None:
    """Pas d'autorisation par defaut : une convention oubliee a la reprise de donnees ne doit pas
    laisser passer des actes que la compagnie n'a jamais delegues."""
    produit = _produit(session, "SI-ESSENTIEL")
    session.execute(
        ConventionProduit.__table__.delete().where(ConventionProduit.produit_id == produit.id)
    )
    session.flush()

    perimetre = perimetre_delegue(session, produit.id, JOUR)
    assert perimetre.convention_reference is None
    assert perimetre.actes == frozenset()
    with pytest.raises(ActeNonDelegue) as refus:
        verifie_acte_delegue(session, produit.id, ActeGestion.AFFILIATION, JOUR)
    assert "aucune convention" in str(refus.value)


def test_une_convention_expiree_ne_permet_plus_rien(session) -> None:
    produit = _produit(session, "SI-ESSENTIEL")
    convention = session.scalars(
        select(ConventionDelegation)
        .join(ConventionProduit, ConventionProduit.convention_id == ConventionDelegation.id)
        .where(ConventionProduit.produit_id == produit.id)
    ).one()
    convention.date_fin_validite = JOUR - timedelta(days=1)
    session.flush()

    with pytest.raises(ActeNonDelegue):
        verifie_acte_delegue(session, produit.id, ActeGestion.AFFILIATION, JOUR)
    # La veille de l'echeance, l'acte passait encore.
    verifie_acte_delegue(session, produit.id, ActeGestion.AFFILIATION, JOUR - timedelta(days=1))


def test_la_portee_totale_declaree_n_autorise_rien_par_elle_meme(session) -> None:
    """Une convention saisie « totale » mais sans ligne pour les prestations ne permet pas de regler une
    prestation. Le libelle sert a l'affichage, la liste des actes seule fait foi."""
    produit = _produit(session, "SI-ESSENTIEL")
    convention = session.scalars(
        select(ConventionDelegation)
        .join(ConventionProduit, ConventionProduit.convention_id == ConventionDelegation.id)
        .where(ConventionProduit.produit_id == produit.id)
    ).one()
    assert convention.portee is PorteeDelegation.TOTALE

    session.execute(
        ActeDelegue.__table__.delete().where(
            ActeDelegue.convention_id == convention.id,
            ActeDelegue.acte == ActeGestion.GESTION_PRESTATIONS,
        )
    )
    session.flush()

    perimetre = perimetre_delegue(session, produit.id, JOUR)
    assert perimetre.portee_declaree == PorteeDelegation.TOTALE.value
    assert not perimetre.autorise(ActeGestion.GESTION_PRESTATIONS)
    with pytest.raises(ActeNonDelegue):
        verifie_acte_delegue(session, produit.id, ActeGestion.GESTION_PRESTATIONS, JOUR)


def test_deux_conventions_qui_se_chevauchent_sont_refusees(session) -> None:
    """Deviner laquelle des deux s'applique serait pire que de s'arreter."""
    produit = _produit(session, "SI-ESSENTIEL")
    doublon = ConventionDelegation(
        reference="CONV-DOUBLON-2024",
        compagnie_id=produit.compagnie_id,
        portee=PorteeDelegation.PARTIELLE,
        date_debut_validite=date(2024, 1, 1),
        date_fin_validite=None,
        commentaire="Convention en doublon, creee par le test",
    )
    session.add(doublon)
    session.flush()
    session.add(ConventionProduit(convention_id=doublon.id, produit_id=produit.id))
    session.flush()

    with pytest.raises(DelegationAmbigue) as refus:
        perimetre_delegue(session, produit.id, JOUR)
    assert "CONV-DOUBLON-2024" in str(refus.value)


# --- Le refus, a travers le service d'ecriture --------------------------------------------------


def test_la_souscription_est_refusee_si_l_affiliation_n_est_pas_deleguee(session, adherent) -> None:
    produit = _produit(session, "SI-ESSENTIEL")
    session.execute(
        ActeDelegue.__table__.delete().where(ActeDelegue.acte == ActeGestion.AFFILIATION)
    )
    session.flush()

    with pytest.raises(ActeNonDelegue):
        service.souscrit_contrat(
            session,
            service.DemandeSouscription(
                numero_adherent=adherent.numero_adherent,
                code_produit=produit.code,
                code_formule="F1",
                code_apporteur="AP01",
                date_souscription=JOUR,
                cotisation_mensuelle_cents=5_000,
                fractionnement=Fractionnement.MENSUEL,
            ),
        )


def test_la_resiliation_est_refusee_si_la_radiation_n_est_pas_deleguee(session, contrat_oceane) -> None:
    """Radier un adherent est un acte qui engage la compagnie : sans delegation, le cabinet ne peut pas."""
    service.met_en_vigueur(session, contrat_oceane, date(2024, 3, 1))
    session.execute(ActeDelegue.__table__.delete().where(ActeDelegue.acte == ActeGestion.RADIATION))
    session.flush()

    from courtage.modeles.enums import MotifResiliation

    with pytest.raises(ActeNonDelegue):
        service.resilie(session, contrat_oceane, JOUR, MotifResiliation.ECHEANCE)


def test_la_delegation_est_appreciee_a_la_date_de_l_acte(session, contrat_oceane) -> None:
    """Une convention qui prend fin en 2025 ne permet pas de saisir un avenant a effet en 2026, meme si
    l'avenant est saisi aujourd'hui."""
    service.met_en_vigueur(session, contrat_oceane, date(2024, 3, 1))
    convention = session.scalars(
        select(ConventionDelegation)
        .join(ConventionProduit, ConventionProduit.convention_id == ConventionDelegation.id)
        .where(ConventionProduit.produit_id == contrat_oceane.produit_id)
    ).one()
    convention.date_fin_validite = date(2025, 12, 31)
    session.flush()

    from courtage.modeles.enums import TypeAvenant

    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.REVALORISATION_TARIFAIRE,
        date_effet=date(2025, 1, 1),
        cotisation_mensuelle_cents=7_000,
    )
    with pytest.raises(ActeNonDelegue):
        service.ajoute_avenant(
            session,
            contrat_oceane,
            type_avenant=TypeAvenant.REVALORISATION_TARIFAIRE,
            date_effet=date(2026, 1, 1),
            cotisation_mensuelle_cents=7_500,
        )


# --- Coherence entre ce que le generateur applique et ce que le domaine autorise -----------------


def test_les_donnees_generees_respectent_le_perimetre_delegue(session) -> None:
    """Aucun flux ne doit exister sur un acte que la compagnie n'a pas delegue.

    La regle est ecrite deux fois : dans `domaine.delegation`, que l'API applique, et a la main dans
    `generateur.financier`, qui decide quels flux produire. Deux implementations d'une meme regle
    finissent toujours par diverger ; ce test les confronte sur les donnees reelles.

    Sans objet sur la base de test, qui ne contient que le referentiel.
    """
    from sqlalchemy import func

    from courtage.modeles.financier import AppelCotisation, Encaissement, Prestation
    from courtage.modeles.portefeuille import Contrat

    if (session.scalar(select(func.count(Contrat.id))) or 0) < 100:
        pytest.skip("base de test sans portefeuille genere")

    produits = list(session.scalars(select(Produit)))
    verifies = 0

    for produit in produits:
        contrats = select(Contrat.id).where(Contrat.produit_id == produit.id).scalar_subquery()

        # Chaque flux est confronte a la delegation **a sa propre date**, et non a une date unique.
        # Un appel emis avant l'expiration d'une convention est parfaitement regulier ; le juger a
        # une date posterieure le declarerait a tort irregulier. Le premier jet de ce test tombait
        # dans ce piege, et le produit a convention echue l'a revele.
        for echeance in session.scalars(
            select(AppelCotisation.date_echeance)
            .where(AppelCotisation.contrat_id.in_(contrats))
            .distinct()
        ):
            assert perimetre_delegue(session, produit.id, echeance).autorise(
                ActeGestion.QUITTANCEMENT
            ), f"{produit.code} : appel emis le {echeance} sans delegation du quittancement"

        for jour in session.scalars(
            select(Encaissement.date_encaissement)
            .where(Encaissement.contrat_id.in_(contrats))
            .distinct()
        ):
            assert perimetre_delegue(session, produit.id, jour).autorise(
                ActeGestion.ENCAISSEMENT
            ), f"{produit.code} : encaissement du {jour} sans delegation de l'encaissement"

        for jour in session.scalars(
            select(Prestation.date_soins).where(Prestation.contrat_id.in_(contrats)).distinct()
        ):
            assert perimetre_delegue(session, produit.id, jour).autorise(
                ActeGestion.GESTION_PRESTATIONS
            ), f"{produit.code} : prestation du {jour} sans delegation de leur gestion"

        verifies += 1

    assert verifies == 8, "les huit produits du referentiel doivent etre verifies"


def test_un_appel_encaisse_porte_bien_un_encaissement(session) -> None:
    """Un appel declare encaisse sans aucune ligne d'encaissement ferait commissionner dans le vide.

    Le generateur tirait le statut avant de savoir si l'encaissement etait delegue : 28 338 appels
    etaient declares encaisses ou partiels sans qu'un seul euro soit connu de l'ERP.
    """
    from sqlalchemy import func

    from courtage.modeles.enums import StatutAppel
    from courtage.modeles.financier import AppelCotisation, Encaissement
    from courtage.modeles.portefeuille import Contrat

    if (session.scalar(select(func.count(Contrat.id))) or 0) < 100:
        pytest.skip("base de test sans portefeuille genere")

    orphelins = session.scalar(
        select(func.count(AppelCotisation.id))
        .outerjoin(Encaissement, Encaissement.appel_id == AppelCotisation.id)
        .where(
            AppelCotisation.statut.in_((StatutAppel.ENCAISSE, StatutAppel.PARTIEL)),
            Encaissement.id.is_(None),
        )
    )
    assert orphelins == 0, f"{orphelins} appels encaisses ou partiels sans ligne d'encaissement"


def test_une_convention_pas_encore_en_vigueur_n_autorise_rien(session) -> None:
    """Le debut de validite d'une convention doit etre respecte, pas seulement sa fin.

    Trou signale par une verification par mutation : ignorer `date_debut_validite` dans la lecture du
    perimetre n'etait detecte par aucun test. Une convention signee pour l'annee prochaine
    autoriserait alors des actes des aujourd'hui, ce qui est exactement l'inverse de ce qu'elle dit.
    """
    produit = _produit(session, "SI-ESSENTIEL")
    convention = session.scalars(
        select(ConventionDelegation)
        .join(ConventionProduit, ConventionProduit.convention_id == ConventionDelegation.id)
        .where(ConventionProduit.produit_id == produit.id)
    ).one()
    convention.date_debut_validite = date(2027, 1, 1)
    session.flush()

    # La veille de l'entree en vigueur, rien n'est autorise.
    perimetre = perimetre_delegue(session, produit.id, date(2026, 12, 31))
    assert perimetre.convention_reference is None
    assert perimetre.actes == frozenset()
    with pytest.raises(ActeNonDelegue):
        verifie_acte_delegue(session, produit.id, ActeGestion.AFFILIATION, date(2026, 12, 31))

    # Le jour meme, elle s'applique.
    verifie_acte_delegue(session, produit.id, ActeGestion.AFFILIATION, date(2027, 1, 1))


def test_la_convention_echue_du_jeu_de_demonstration_refuse_bien(session) -> None:
    """Le referentiel genere pose une convention arrivee a echeance, pour rendre le refus constatable."""
    produit = _produit(session, "PV-ARRET")
    avant = perimetre_delegue(session, produit.id, date(2026, 6, 30))
    apres = perimetre_delegue(session, produit.id, date(2026, 7, 1))

    assert avant.actes, "la convention couvrait bien le produit avant son echeance"
    assert apres.actes == frozenset(), "plus aucun acte n'est delegue apres l'echeance"
    with pytest.raises(ActeNonDelegue) as refus:
        verifie_acte_delegue(session, produit.id, ActeGestion.AVENANT, date(2026, 7, 1))
    assert "aucune convention" in str(refus.value)
