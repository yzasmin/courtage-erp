"""Tests du cycle de vie du contrat : ce qui est autorise, ce qui est refuse, et pourquoi.

Critere d'acceptation du module 1 : « tests sur les transitions de statut ». Chaque transition possible
est exercee, et chaque transition interdite est verifiee comme refusee, avec son exception propre.
"""

from __future__ import annotations

from datetime import date

import pytest

from courtage.domaine.cycle_vie import (
    TRANSITIONS_AUTORISEES,
    ContratResilie,
    MotifResiliationManquant,
    TransitionInterdite,
    transition_possible,
    verifie_transition,
)
from courtage.modeles.enums import MotifResiliation, StatutContrat, TypeAvenant
from courtage.services import contrats as service

DATE_EFFET = date(2024, 3, 1)


# --- La table des transitions, verifiee exhaustivement ------------------------------------------

TRANSITIONS_ATTENDUES = {
    (StatutContrat.DEVIS, StatutContrat.EN_COURS): True,
    (StatutContrat.DEVIS, StatutContrat.SUSPENDU): False,
    (StatutContrat.DEVIS, StatutContrat.RESILIE): False,
    (StatutContrat.EN_COURS, StatutContrat.SUSPENDU): True,
    (StatutContrat.EN_COURS, StatutContrat.RESILIE): True,
    (StatutContrat.EN_COURS, StatutContrat.DEVIS): False,
    (StatutContrat.SUSPENDU, StatutContrat.EN_COURS): True,
    (StatutContrat.SUSPENDU, StatutContrat.RESILIE): True,
    (StatutContrat.SUSPENDU, StatutContrat.DEVIS): False,
    (StatutContrat.RESILIE, StatutContrat.EN_COURS): False,
    (StatutContrat.RESILIE, StatutContrat.SUSPENDU): False,
    (StatutContrat.RESILIE, StatutContrat.DEVIS): False,
}


@pytest.mark.parametrize(("couple", "attendu"), sorted(TRANSITIONS_ATTENDUES.items()))
def test_table_des_transitions(couple: tuple[StatutContrat, StatutContrat], attendu: bool) -> None:
    depart, arrivee = couple
    assert transition_possible(depart, arrivee) is attendu


def test_tous_les_statuts_sont_declares() -> None:
    """Un statut ajoute a l'enumeration sans entree dans la table ferait planter la verification."""
    assert set(TRANSITIONS_AUTORISEES) == set(StatutContrat)


def test_un_contrat_resilie_est_terminal() -> None:
    assert TRANSITIONS_AUTORISEES[StatutContrat.RESILIE] == frozenset()


# --- Le domaine, sans base ---------------------------------------------------------------------


def test_resiliation_sans_motif_est_refusee() -> None:
    with pytest.raises(MotifResiliationManquant):
        verifie_transition(
            StatutContrat.EN_COURS, StatutContrat.RESILIE, TypeAvenant.RESILIATION, motif_resiliation=None
        )


def test_resiliation_avec_motif_est_acceptee() -> None:
    verifie_transition(
        StatutContrat.EN_COURS,
        StatutContrat.RESILIE,
        TypeAvenant.RESILIATION,
        motif_resiliation=MotifResiliation.ECHEANCE,
    )


def test_un_devis_ne_se_resilie_pas() -> None:
    """Un devis n'a jamais pris effet : il n'y a rien a resilier, et le compter comme une resiliation
    fausserait le taux de resiliation, dont le denominateur est le portefeuille en vigueur."""
    with pytest.raises(TransitionInterdite):
        verifie_transition(
            StatutContrat.DEVIS,
            StatutContrat.RESILIE,
            TypeAvenant.RESILIATION,
            motif_resiliation=MotifResiliation.ECHEANCE,
        )


def test_un_contrat_resilie_n_accepte_plus_d_avenant() -> None:
    with pytest.raises(ContratResilie):
        verifie_transition(
            StatutContrat.RESILIE, StatutContrat.EN_COURS, TypeAvenant.REMISE_EN_VIGUEUR
        )


def test_le_type_d_avenant_doit_correspondre_a_la_transition() -> None:
    """Une « revalorisation tarifaire » qui resilierait serait un mensonge dans la piste d'audit."""
    with pytest.raises(TransitionInterdite):
        verifie_transition(
            StatutContrat.EN_COURS,
            StatutContrat.RESILIE,
            TypeAvenant.REVALORISATION_TARIFAIRE,
            motif_resiliation=MotifResiliation.ECHEANCE,
        )


def test_un_avenant_de_modification_ne_change_pas_le_statut() -> None:
    verifie_transition(
        StatutContrat.EN_COURS, StatutContrat.EN_COURS, TypeAvenant.CHANGEMENT_FORMULE
    )
    with pytest.raises(TransitionInterdite):
        verifie_transition(
            StatutContrat.EN_COURS, StatutContrat.SUSPENDU, TypeAvenant.CHANGEMENT_FORMULE
        )


# --- Les memes regles, a travers le service et la base ------------------------------------------


def test_souscription_cree_un_devis_sans_date_effet(session, contrat_oceane) -> None:
    assert contrat_oceane.statut is StatutContrat.DEVIS
    assert contrat_oceane.date_effet is None
    assert contrat_oceane.date_resiliation is None
    avenants = list(contrat_oceane.avenants)
    assert len(avenants) == 1
    assert avenants[0].numero_ordre == 0
    assert avenants[0].type_avenant is TypeAvenant.SOUSCRIPTION


def test_mise_en_vigueur_donne_sa_date_effet_au_contrat(session, contrat_oceane) -> None:
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    assert contrat_oceane.statut is StatutContrat.EN_COURS
    assert contrat_oceane.date_effet == DATE_EFFET


def test_parcours_complet_suspension_puis_remise_puis_resiliation(session, contrat_oceane) -> None:
    """Le parcours reel d'un impaye : mise en demeure, suspension, regularisation, puis sortie."""
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    service.suspend(session, contrat_oceane, date(2025, 2, 1))
    assert contrat_oceane.statut is StatutContrat.SUSPENDU

    service.remet_en_vigueur(session, contrat_oceane, date(2025, 4, 1))
    assert contrat_oceane.statut is StatutContrat.EN_COURS

    service.resilie(session, contrat_oceane, date(2026, 1, 1), MotifResiliation.ECHEANCE)
    assert contrat_oceane.statut is StatutContrat.RESILIE
    assert contrat_oceane.date_resiliation == date(2026, 1, 1)
    assert contrat_oceane.motif_resiliation is MotifResiliation.ECHEANCE
    # Cinq avenants : souscription, mise en vigueur, suspension, remise, resiliation.
    assert [a.numero_ordre for a in contrat_oceane.avenants] == [0, 1, 2, 3, 4]


def test_resilier_un_devis_est_refuse_par_le_service(session, contrat_oceane) -> None:
    with pytest.raises(TransitionInterdite):
        service.resilie(session, contrat_oceane, DATE_EFFET, MotifResiliation.ECHEANCE)


def test_un_contrat_resilie_refuse_un_nouvel_avenant(session, contrat_oceane) -> None:
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    service.resilie(session, contrat_oceane, date(2025, 6, 1), MotifResiliation.NON_PAIEMENT)
    with pytest.raises(ContratResilie):
        service.remet_en_vigueur(session, contrat_oceane, date(2025, 7, 1))


def test_un_avenant_ne_peut_pas_preceder_le_precedent(session, contrat_oceane) -> None:
    """Un historique dont les dates d'effet ne sont pas croissantes rendrait la reconstitution ambigue."""
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    with pytest.raises(service.DateAvenantIncoherente):
        service.suspend(session, contrat_oceane, date(2023, 1, 1))


def test_chaque_changement_de_statut_laisse_un_avenant(session, contrat_oceane) -> None:
    """Exigence de piste d'audit : aucun statut ne change sans l'acte qui le porte."""
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    service.suspend(session, contrat_oceane, date(2025, 2, 1))
    service.resilie(session, contrat_oceane, date(2025, 5, 1), MotifResiliation.NON_PAIEMENT)

    session.refresh(contrat_oceane)
    statuts_des_avenants = [a.statut for a in contrat_oceane.avenants]
    assert statuts_des_avenants == [
        StatutContrat.DEVIS,
        StatutContrat.EN_COURS,
        StatutContrat.SUSPENDU,
        StatutContrat.RESILIE,
    ]
    # Le statut du contrat est celui du dernier avenant, jamais autre chose.
    assert contrat_oceane.statut is statuts_des_avenants[-1]


def test_le_type_d_avenant_est_refuse_a_travers_le_service(session, contrat_oceane) -> None:
    """Le controle du type d'avenant doit vivre jusque dans le service, pas seulement dans le domaine.

    Trou signale par une verification par mutation : le controle
    `TYPE_ATTENDU_PAR_TRANSITION` pouvait etre supprime sans qu'aucun test echoue, parce que seul le
    domaine etait exerce. Un avenant etiquete « revalorisation tarifaire » qui resilie le contrat
    serait un mensonge dans la piste d'audit, et c'est precisement ce qu'un controle de compagnie
    cherche.
    """
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    # Le type choisi change bien un statut, mais pas celui-la : c'est ce qui exerce la table
    # `TYPE_ATTENDU_PAR_TRANSITION`. Un type qui ne change aucun statut serait refuse plus tot, par
    # une autre regle, et ne prouverait donc rien sur celle-ci. La verification par mutation a
    # montre que le premier jet de ce test tombait precisement dans ce piege.
    with pytest.raises(TransitionInterdite, match="type"):
        service.ajoute_avenant(
            session,
            contrat_oceane,
            type_avenant=TypeAvenant.MISE_EN_VIGUEUR,
            date_effet=date(2025, 6, 1),
            statut_cible=StatutContrat.RESILIE,
            motif_resiliation=MotifResiliation.ECHEANCE,
        )
    # Aucune ecriture ne survit au refus : la piste d'audit reste intacte.
    session.refresh(contrat_oceane)
    assert contrat_oceane.statut is StatutContrat.EN_COURS
    assert [a.type_avenant for a in contrat_oceane.avenants] == [
        TypeAvenant.SOUSCRIPTION,
        TypeAvenant.MISE_EN_VIGUEUR,
    ]


def test_une_suspension_etiquetee_remise_en_vigueur_est_refusee(session, contrat_oceane) -> None:
    """Meme controle, dans l'autre sens : l'etiquette doit decrire ce que l'acte fait."""
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    with pytest.raises(TransitionInterdite):
        service.ajoute_avenant(
            session,
            contrat_oceane,
            type_avenant=TypeAvenant.REMISE_EN_VIGUEUR,
            date_effet=date(2025, 6, 1),
            statut_cible=StatutContrat.SUSPENDU,
        )
