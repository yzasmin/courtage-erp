"""Tests de l'integrite en base : les contraintes refusent-elles vraiment les ecritures incoherentes.

Ces tests ne passent pas par les services : ils ecrivent directement, pour verifier que la **base** se
defend, et pas seulement le code applicatif. Un ERP recoit des ecritures par des imports, des scripts de
reprise et des correctifs manuels ; une regle qui ne vit que dans le service applicatif sera contournee
un jour.

Ils tournent par defaut sur SQLite, et par consequent ils verifient aussi que le pragma des cles
etrangeres est bien pose : sans lui, SQLite accepterait une cle etrangere inexistante.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from courtage.modeles.enums import Fractionnement, MotifResiliation, StatutAppel, StatutContrat
from courtage.modeles.financier import AppelCotisation, Prestation
from courtage.modeles.portefeuille import Avenant, Contrat
from courtage.modeles.referentiel import Formule, Produit
from courtage.services import contrats as service

DATE_EFFET = date(2024, 3, 1)


def _ids_referentiel(session) -> tuple[int, int, int]:
    produit = session.scalars(select(Produit).where(Produit.code == "SI-ESSENTIEL")).one()
    formule = session.scalars(
        select(Formule).where(Formule.produit_id == produit.id, Formule.code == "F1")
    ).one()
    from courtage.modeles.referentiel import Apporteur

    apporteur = session.scalars(select(Apporteur).where(Apporteur.code == "AP01")).one()
    return produit.id, formule.id, apporteur.id


def _contrat_brut(session, adherent, **remplacements) -> Contrat:
    produit_id, formule_id, apporteur_id = _ids_referentiel(session)
    valeurs = {
        "numero_contrat": "SI-2024-99999",
        "adherent_id": adherent.id,
        "entreprise_id": None,
        "produit_id": produit_id,
        "statut": StatutContrat.EN_COURS,
        "date_souscription": date(2024, 2, 10),
        "date_effet": DATE_EFFET,
        "date_resiliation": None,
        "motif_resiliation": None,
        "formule_id": formule_id,
        "apporteur_id": apporteur_id,
        "cotisation_mensuelle_cents": 6_000,
        "fractionnement": Fractionnement.MENSUEL,
    }
    valeurs.update(remplacements)
    return Contrat(**valeurs)


# --- Cles etrangeres ----------------------------------------------------------------------------


def test_les_cles_etrangeres_sont_bien_appliquees(session, adherent) -> None:
    """Sans le pragma `foreign_keys = ON`, SQLite accepterait cet adherent inexistant, le test local
    passerait, et l'anomalie n'apparaitrait qu'en production sur PostgreSQL."""
    session.add(_contrat_brut(session, adherent, adherent_id=999_999))
    with pytest.raises(IntegrityError):
        session.flush()


def test_le_pragma_est_pose_sur_la_connexion(session) -> None:
    if session.get_bind().dialect.name != "sqlite":
        pytest.skip("controle specifique a SQLite")
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


# --- Unicite ------------------------------------------------------------------------------------


def test_le_numero_de_contrat_est_unique(session, adherent) -> None:
    session.add(_contrat_brut(session, adherent))
    session.flush()
    session.add(_contrat_brut(session, adherent))
    with pytest.raises(IntegrityError):
        session.flush()


def test_deux_avenants_ne_partagent_pas_un_rang(session, contrat_oceane) -> None:
    """L'unicite du couple contrat et rang est ce qui rend l'historique non ambigu."""
    _, formule_id, apporteur_id = _ids_referentiel(session)
    session.add(
        Avenant(
            contrat_id=contrat_oceane.id,
            numero_ordre=0,
            type_avenant="revalorisation_tarifaire",
            date_effet=DATE_EFFET,
            date_saisie=DATE_EFFET,
            statut=StatutContrat.DEVIS,
            formule_id=formule_id,
            apporteur_id=apporteur_id,
            cotisation_mensuelle_cents=7_000,
            fractionnement=Fractionnement.MENSUEL,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_un_contrat_n_est_pas_quittance_deux_fois_pour_la_meme_periode(session, contrat_oceane) -> None:
    for _ in range(2):
        session.add(
            AppelCotisation(
                reference_appel=f"APP-TEST-{_}",
                contrat_id=contrat_oceane.id,
                periode_debut=date(2025, 1, 1),
                periode_fin=date(2025, 1, 31),
                date_echeance=date(2025, 1, 1),
                montant_ht_cents=6_000,
                montant_taxe_cents=796,
                montant_total_cents=6_796,
                taux_taxe_bp=1_327,
                statut=StatutAppel.ATTENDU,
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


# --- Contraintes de verification ----------------------------------------------------------------


def test_un_devis_ne_peut_pas_porter_de_date_effet(session, adherent) -> None:
    session.add(
        _contrat_brut(session, adherent, statut=StatutContrat.DEVIS, date_effet=DATE_EFFET)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_un_contrat_en_cours_doit_porter_une_date_effet(session, adherent) -> None:
    session.add(_contrat_brut(session, adherent, statut=StatutContrat.EN_COURS, date_effet=None))
    with pytest.raises(IntegrityError):
        session.flush()


def test_une_resiliation_sans_motif_est_refusee_par_la_base(session, adherent) -> None:
    """L'exigence de la specification est portee par la base, et pas seulement par l'API : aucun chemin
    d'ecriture ne peut y echapper."""
    session.add(
        _contrat_brut(
            session,
            adherent,
            statut=StatutContrat.RESILIE,
            date_resiliation=date(2025, 6, 1),
            motif_resiliation=None,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_une_resiliation_sans_date_est_refusee_par_la_base(session, adherent) -> None:
    session.add(
        _contrat_brut(
            session,
            adherent,
            statut=StatutContrat.RESILIE,
            date_resiliation=None,
            motif_resiliation=MotifResiliation.ECHEANCE,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_un_contrat_non_resilie_ne_porte_pas_de_motif(session, adherent) -> None:
    session.add(
        _contrat_brut(session, adherent, motif_resiliation=MotifResiliation.ECHEANCE)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_une_cotisation_negative_est_refusee(session, adherent) -> None:
    session.add(_contrat_brut(session, adherent, cotisation_mensuelle_cents=-1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_la_resiliation_ne_precede_pas_la_date_effet(session, adherent) -> None:
    session.add(
        _contrat_brut(
            session,
            adherent,
            statut=StatutContrat.RESILIE,
            date_resiliation=date(2023, 1, 1),
            motif_resiliation=MotifResiliation.ECHEANCE,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_le_total_d_un_appel_egale_la_part_hors_taxe_plus_la_taxe(session, contrat_oceane) -> None:
    """Contrainte posee pour que la colonne de total, qui sert aux sommes de pilotage, ne puisse pas
    mentir."""
    session.add(
        AppelCotisation(
            reference_appel="APP-TEST-FAUX",
            contrat_id=contrat_oceane.id,
            periode_debut=date(2025, 2, 1),
            periode_fin=date(2025, 2, 28),
            date_echeance=date(2025, 2, 1),
            montant_ht_cents=6_000,
            montant_taxe_cents=796,
            montant_total_cents=9_999,
            taux_taxe_bp=1_327,
            statut=StatutAppel.ATTENDU,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_on_ne_rembourse_pas_plus_que_le_montant_demande(session, contrat_oceane, adherent) -> None:
    from courtage.modeles.referentiel import Garantie

    garantie = session.scalars(select(Garantie).where(Garantie.code == "OPTIQUE")).one()
    session.add(
        Prestation(
            reference_prestation="PRE-TEST-TROP",
            contrat_id=contrat_oceane.id,
            adherent_id=adherent.id,
            garantie_id=garantie.id,
            date_soins=date(2025, 3, 10),
            date_reglement=date(2025, 3, 20),
            montant_demande_cents=20_000,
            montant_rembourse_cents=30_000,
            statut="reglee",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_une_prestation_rejetee_ne_rembourse_rien_et_porte_un_motif(session, contrat_oceane, adherent) -> None:
    from courtage.modeles.referentiel import Garantie

    garantie = session.scalars(select(Garantie).where(Garantie.code == "OPTIQUE")).one()
    session.add(
        Prestation(
            reference_prestation="PRE-TEST-REJET",
            contrat_id=contrat_oceane.id,
            adherent_id=adherent.id,
            garantie_id=garantie.id,
            date_soins=date(2025, 3, 10),
            date_reglement=None,
            montant_demande_cents=20_000,
            montant_rembourse_cents=5_000,
            statut="rejetee",
            motif_rejet="hors garantie",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_un_bordereau_a_exactement_un_destinataire(session) -> None:
    """Un bordereau de commissions vient d'une compagnie, un bordereau de retrocessions part vers un
    apporteur. Jamais les deux, jamais aucun."""
    from courtage.modeles.financier import Bordereau

    session.add(
        Bordereau(
            reference="BOR-TEST-SANS",
            type_bordereau="commissions",
            periode=date(2025, 1, 1),
            date_emission=date(2025, 2, 5),
            compagnie_id=None,
            apporteur_id=None,
            nombre_lignes=0,
            montant_total_cents=0,
            statut="en_preparation",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


# --- Index attendus sur les cles de recherche ---------------------------------------------------


#: Index attendus, table par table. Chacun correspond a une requete d'ecran, listee dans
#: `docs/modele-donnees.md`.
INDEX_ATTENDUS = (
    ("contrat", "ix_contrat_statut_effet"),
    ("contrat", "ix_contrat_apporteur_statut"),
    ("adherent", "ix_adherent_nom_prenom"),
    ("avenant", "ix_avenant_contrat_effet"),
    ("appel_cotisation", "ix_appel_cotisation_contrat_echeance"),
    ("prestation", "ix_prestation_contrat_soins"),
    ("retrocession", "ix_retrocession_apporteur_periode"),
)


@pytest.mark.parametrize(("table", "index"), INDEX_ATTENDUS)
def test_les_cles_de_recherche_sont_indexees_en_base(session, table: str, index: str) -> None:
    """Les colonnes par lesquelles un gestionnaire cherche doivent etre indexees **dans la base**.

    Ce test lisait `Base.metadata`, c'est-a-dire les declarations Python. Il passait donc sans aucune
    base de donnees, et une migration qui aurait oublie un index l'aurait laisse vert. C'est le genre
    de test qui rassure sans rien garantir.
    """
    from sqlalchemy import inspect as inspecte

    poses = {i["name"] for i in inspecte(session.get_bind()).get_indexes(table)}
    assert index in poses, f"l'index {index} est absent de la table {table} : {sorted(poses)}"


def test_le_schema_migre_correspond_au_modele(session) -> None:
    """Aucune derive entre les entites declarees et le schema que les migrations produisent.

    Sans ce controle, une colonne ajoutee au modele sans migration ne casserait aucun test, et le
    defaut se decouvrirait au deploiement chez un client.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from courtage.modeles import Base

    contexte = MigrationContext.configure(session.connection())
    differences = compare_metadata(contexte, Base.metadata)
    # Les index que la base ajoute d'elle-meme pour les contraintes d'unicite ne sont pas une derive.
    reelles = [d for d in differences if not (isinstance(d, tuple) and d[0] in ("add_index", "remove_index"))]
    assert reelles == [], f"le schema migre diverge du modele : {reelles}"


def test_le_service_refuse_une_cotisation_negative(session, adherent) -> None:
    """La meme regle existe cote service, pour que le refus porte un message lisible plutot qu'une
    violation de contrainte."""
    with pytest.raises(service.ReferenceInvalide):
        service.souscrit_contrat(
            session,
            service.DemandeSouscription(
                numero_adherent=adherent.numero_adherent,
                code_produit="SI-ESSENTIEL",
                code_formule="F1",
                code_apporteur="AP01",
                date_souscription=date(2024, 2, 10),
                cotisation_mensuelle_cents=-500,
                fractionnement=Fractionnement.MENSUEL,
            ),
        )


def test_une_formule_d_un_autre_produit_est_refusee(session, contrat_oceane) -> None:
    """Rattacher a un contrat une formule qui appartient a un autre produit donnerait un contrat
    incoherent, dont les garanties affichees ne seraient pas celles du produit."""
    autre = session.scalars(
        select(Formule).join(Produit, Produit.id == Formule.produit_id).where(Produit.code == "PV-DECES")
    ).first()
    from courtage.modeles.enums import TypeAvenant

    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    with pytest.raises(service.ReferenceInvalide):
        service.ajoute_avenant(
            session,
            contrat_oceane,
            type_avenant=TypeAvenant.CHANGEMENT_FORMULE,
            date_effet=date(2025, 1, 1),
            formule_id=autre.id,
        )
