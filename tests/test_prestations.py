"""Tests de l'enregistrement d'une prestation : delegation, garantie a la date, plafond cumule.

Ce fichier ferme un ecart signale par la verification : la documentation annoncait un controle de
delegation avant la gestion des prestations, sans qu'aucun chemin d'ecriture ne l'applique. Il est
desormais applique par `services.prestations`, et verifie ici.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from courtage.domaine.delegation import ActeNonDelegue
from courtage.modeles.enums import Fractionnement, MotifResiliation, StatutPrestation
from courtage.services import contrats as service_contrats
from courtage.services import prestations as service
from courtage.services.contrats import DemandeSouscription, ReferenceInvalide, souscrit_contrat

DATE_SOUSCRIPTION = date(2024, 2, 10)
DATE_EFFET = date(2024, 3, 1)
DATE_SOINS = date(2025, 5, 12)


@pytest.fixture
def contrat_en_vigueur(session, contrat_oceane):
    """Un contrat Oceane en vigueur : cette compagnie delegue la gestion des prestations."""
    service_contrats.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    return contrat_oceane


def _demande(numero: str, code_garantie: str = "OPTIQUE", montant: int = 20_000, jour: date = DATE_SOINS):
    return service.DemandePrestation(
        numero_contrat=numero,
        code_garantie=code_garantie,
        date_soins=jour,
        montant_demande_cents=montant,
    )


# --- Delegation ---------------------------------------------------------------------------------


def test_une_prestation_passe_quand_la_gestion_est_deleguee(session, contrat_en_vigueur) -> None:
    resultat = service.enregistre_prestation(
        session, _demande(contrat_en_vigueur.numero_contrat), "PRE-TEST-0000001"
    )
    assert resultat.prestation.statut is StatutPrestation.REGLEE
    assert resultat.prestation.montant_rembourse_cents > 0


def test_une_prestation_est_refusee_quand_la_gestion_n_est_pas_deleguee(
    session, adherent
) -> None:
    """Littoral ne delegue pas la gestion des prestations : un sinistre de prevoyance suppose une
    expertise medicale, que l'assureur garde."""
    contrat = souscrit_contrat(
        session,
        DemandeSouscription(
            numero_adherent=adherent.numero_adherent,
            code_produit="PV-DECES",
            code_formule="F1",
            code_apporteur="AP03",
            date_souscription=DATE_SOUSCRIPTION,
            cotisation_mensuelle_cents=2_400,
            fractionnement=Fractionnement.MENSUEL,
        ),
    )
    service_contrats.met_en_vigueur(session, contrat, DATE_EFFET)

    with pytest.raises(ActeNonDelegue) as refus:
        service.enregistre_prestation(
            session, _demande(contrat.numero_contrat, "DECES", 500_000), "PRE-TEST-0000002"
        )
    assert "prestations" in str(refus.value)


def test_le_refus_de_prestation_repond_409(client, session, adherent) -> None:
    contrat = souscrit_contrat(
        session,
        DemandeSouscription(
            numero_adherent=adherent.numero_adherent,
            code_produit="PV-DECES",
            code_formule="F1",
            code_apporteur="AP03",
            date_souscription=DATE_SOUSCRIPTION,
            cotisation_mensuelle_cents=2_400,
            fractionnement=Fractionnement.MENSUEL,
        ),
    )
    service_contrats.met_en_vigueur(session, contrat, DATE_EFFET)

    reponse = client.post(
        f"/api/v1/contrats/{contrat.numero_contrat}/prestations",
        json={"code_garantie": "DECES", "date_soins": DATE_SOINS.isoformat(), "montant_demande_cents": 500_000},
    )
    assert reponse.status_code == 409
    assert reponse.json()["erreur"]["code"] == "acte_non_delegue"


def test_deux_saisies_sur_un_mois_anterieur_ne_collisionnent_pas(
    client, session, contrat_en_vigueur
) -> None:
    """Deux prestations saisies sur un mois anterieur au dernier mois present en base.

    C'est le defaut qui rendait l'API inutilisable des la deuxieme saisie. `reference_suivante`
    prenait `max(reference_prestation)` toutes periodes confondues, et ce maximum porte d'abord sur le
    mois inscrit dans la reference. Avec une prestation de septembre deja en base, une saisie de
    juillet produisait `PRE-202607-<compteur de septembre + 1>` ; la saisie suivante, toujours en
    juillet, relisait le meme maximum de septembre et reproduisait la meme reference. La contrainte
    d'unicite refusait l'ecriture et l'exception sortait en HTTP 500, en texte brut.

    Le test pose d'abord une prestation sur un mois **posterieur**, puis en saisit deux sur un mois
    anterieur, et exige deux references distinctes et deux reponses 201.
    """
    numero = contrat_en_vigueur.numero_contrat
    mois_recent = date(2025, 9, 8)
    mois_ancien = date(2025, 7, 3)

    premiere = client.post(
        f"/api/v1/contrats/{numero}/prestations",
        json={
            "code_garantie": "OPTIQUE",
            "date_soins": mois_recent.isoformat(),
            "montant_demande_cents": 12_000,
        },
    )
    assert premiere.status_code == 201, premiere.text

    reponses = [
        client.post(
            f"/api/v1/contrats/{numero}/prestations",
            json={
                "code_garantie": "SOINS",
                "date_soins": mois_ancien.isoformat(),
                "montant_demande_cents": 4_000,
            },
        )
        for _ in range(2)
    ]
    for rang, reponse in enumerate(reponses, start=1):
        assert reponse.status_code == 201, (
            f"la saisie {rang} sur un mois anterieur doit aboutir, reponse recue : {reponse.text}"
        )

    references = [reponse.json()["reference_prestation"] for reponse in reponses]
    assert references[0] != references[1], (
        f"les deux saisies du meme mois ont recu la meme reference : {references[0]}"
    )
    assert all(reference.startswith("PRE-202507-") for reference in references), (
        f"la reference doit porter le mois des soins, et non celui de la derniere prestation en base :"
        f" {references}"
    )


# --- Garantie a la date des soins ----------------------------------------------------------------


def test_un_contrat_resilie_n_ouvre_droit_a_rien(session, contrat_en_vigueur) -> None:
    service_contrats.resilie(session, contrat_en_vigueur, date(2025, 1, 1), MotifResiliation.ECHEANCE)
    with pytest.raises(service.ContratSansGarantie):
        service.enregistre_prestation(
            session, _demande(contrat_en_vigueur.numero_contrat), "PRE-TEST-0000003"
        )


def test_un_contrat_suspendu_n_ouvre_droit_a_rien(session, contrat_en_vigueur) -> None:
    """La garantie est suspendue : un remboursement servi a cette date serait repris par la compagnie."""
    service_contrats.suspend(session, contrat_en_vigueur, date(2025, 1, 1))
    with pytest.raises(service.ContratSansGarantie):
        service.enregistre_prestation(
            session, _demande(contrat_en_vigueur.numero_contrat), "PRE-TEST-0000004"
        )


def test_une_prestation_avant_la_mise_en_vigueur_est_refusee(session, contrat_oceane) -> None:
    with pytest.raises(service.ContratSansGarantie):
        service.enregistre_prestation(
            session,
            _demande(contrat_oceane.numero_contrat, jour=DATE_SOUSCRIPTION),
            "PRE-TEST-0000005",
        )


def test_une_garantie_hors_formule_est_refusee(session, contrat_en_vigueur) -> None:
    """Un contrat de sante ne couvre pas le capital deces."""
    with pytest.raises(service.GarantieNonCouverte):
        service.enregistre_prestation(
            session, _demande(contrat_en_vigueur.numero_contrat, "DECES"), "PRE-TEST-0000006"
        )


def test_une_garantie_inconnue_est_refusee(session, contrat_en_vigueur) -> None:
    with pytest.raises(ReferenceInvalide):
        service.enregistre_prestation(
            session, _demande(contrat_en_vigueur.numero_contrat, "INEXISTANT"), "PRE-TEST-0000007"
        )


# --- Plafond annuel cumule -------------------------------------------------------------------------


def test_le_plafond_annuel_se_consomme_sur_l_annee(session, contrat_en_vigueur) -> None:
    """Le plafond s'epuise au fil des soins de l'annee, il ne s'applique pas a chaque prestation.

    C'est le defaut que la verification avait releve : applique prestation par prestation, le plafond
    etait offert autant de fois qu'il y avait de soins.
    """
    from courtage.modeles.referentiel import FormuleGarantie, Garantie

    garantie = session.scalars(select(Garantie).where(Garantie.code == "OPTIQUE")).one()
    couverture = session.scalars(
        select(FormuleGarantie).where(
            FormuleGarantie.formule_id == contrat_en_vigueur.formule_id,
            FormuleGarantie.garantie_id == garantie.id,
        )
    ).one()
    plafond = couverture.plafond_annuel_cents
    assert plafond is not None, "la garantie optique doit etre plafonnee"

    # Une demande suffisamment grosse pour saturer le plafond d'un coup.
    enorme = plafond * 10
    premier = service.enregistre_prestation(
        session, _demande(contrat_en_vigueur.numero_contrat, "OPTIQUE", enorme), "PRE-TEST-0000010"
    )
    assert premier.prestation.montant_rembourse_cents == plafond

    # La deuxieme demande de la meme annee ne rembourse plus rien : le plafond est consomme.
    second = service.enregistre_prestation(
        session, _demande(contrat_en_vigueur.numero_contrat, "OPTIQUE", enorme), "PRE-TEST-0000011"
    )
    assert second.prestation.statut is StatutPrestation.REJETEE
    assert second.prestation.montant_rembourse_cents == 0
    assert second.prestation.motif_rejet == "plafond annuel de la garantie atteint"

    # L'annee suivante, le plafond est de nouveau disponible.
    annee_suivante = service.enregistre_prestation(
        session,
        _demande(contrat_en_vigueur.numero_contrat, "OPTIQUE", enorme, date(2026, 2, 3)),
        "PRE-TEST-0000012",
    )
    assert annee_suivante.prestation.montant_rembourse_cents == plafond


def test_une_prestation_integralement_plafonnee_est_un_rejet_motive(session, contrat_en_vigueur) -> None:
    """Et non un reglement a zero euro, qui laisserait croire a un remboursement effectue."""
    from courtage.modeles.referentiel import FormuleGarantie, Garantie

    garantie = session.scalars(select(Garantie).where(Garantie.code == "OPTIQUE")).one()
    couverture = session.scalars(
        select(FormuleGarantie).where(
            FormuleGarantie.formule_id == contrat_en_vigueur.formule_id,
            FormuleGarantie.garantie_id == garantie.id,
        )
    ).one()
    enorme = couverture.plafond_annuel_cents * 10
    service.enregistre_prestation(
        session, _demande(contrat_en_vigueur.numero_contrat, "OPTIQUE", enorme), "PRE-TEST-0000020"
    )
    rejetee = service.enregistre_prestation(
        session, _demande(contrat_en_vigueur.numero_contrat, "OPTIQUE", enorme), "PRE-TEST-0000021"
    )
    assert rejetee.prestation.statut is StatutPrestation.REJETEE
    assert rejetee.prestation.date_reglement is None
    assert rejetee.prestation.motif_rejet


def test_on_ne_rembourse_jamais_plus_que_les_frais_engages(session, contrat_en_vigueur) -> None:
    """Le taux porte sur la base de remboursement et peut depasser 100 %, mais le remboursement
    reste borne par la depense reelle."""
    resultat = service.enregistre_prestation(
        session, _demande(contrat_en_vigueur.numero_contrat, "SOINS", 5_000), "PRE-TEST-0000030"
    )
    assert resultat.taux_remboursement_bp > 10_000, "les soins courants sont couverts au-dela de 100 %"
    assert resultat.prestation.montant_rembourse_cents <= 5_000
