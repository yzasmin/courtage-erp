"""Tests de l'historisation par avenants et de la reconstitution de l'etat a une date.

Critere d'acceptation du module 1 : « tests sur la reconstitution a date ». Les cas couverts sont ceux
qui comptent en gestion : avant la souscription, entre deux avenants, le jour meme d'un avenant, apres le
dernier, et deux avenants partageant une date d'effet.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from courtage.domaine.avenants import EtatIntrouvable, avenant_en_vigueur, etat_a_la_date
from courtage.modeles.enums import MotifResiliation, StatutContrat, TypeAvenant
from courtage.modeles.portefeuille import Avenant, Contrat
from courtage.modeles.referentiel import Formule
from courtage.services import contrats as service

DATE_SOUSCRIPTION = date(2024, 2, 10)
DATE_EFFET = date(2024, 3, 1)
DATE_REVALORISATION = date(2025, 1, 1)
DATE_RESILIATION = date(2026, 1, 1)
#: Date d'observation des tests qui parcourent le portefeuille. Fixe, pour que le resultat ne depende
#: pas du jour ou la suite est lancee.
DATE_OBSERVATION = date(2026, 9, 30)

COTISATION_INITIALE = 6_840
COTISATION_REVALORISEE = 7_250


@pytest.fixture
def contrat_avec_histoire(session, contrat_oceane):
    """Un contrat complet : souscription, mise en vigueur, revalorisation, puis resiliation."""
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.REVALORISATION_TARIFAIRE,
        date_effet=DATE_REVALORISATION,
        cotisation_mensuelle_cents=COTISATION_REVALORISEE,
        commentaire="Revalorisation a l'echeance",
    )
    service.resilie(session, contrat_oceane, DATE_RESILIATION, MotifResiliation.ECHEANCE)
    return contrat_oceane


def test_avant_la_souscription_il_n_y_a_pas_d_etat(session, contrat_avec_histoire) -> None:
    """Repondre « statut inconnu » serait plus commode, mais un ecran qui affiche un etat vide pour une
    date anterieure au contrat induit en erreur."""
    with pytest.raises(EtatIntrouvable):
        etat_a_la_date(session, contrat_avec_histoire, DATE_SOUSCRIPTION - timedelta(days=1))


def test_le_jour_de_la_souscription_le_contrat_est_un_devis(session, contrat_avec_histoire) -> None:
    etat = etat_a_la_date(session, contrat_avec_histoire, DATE_SOUSCRIPTION)
    assert etat.statut is StatutContrat.DEVIS
    assert etat.est_en_portefeuille is False
    assert etat.avenant_numero_ordre == 0


def test_entre_la_mise_en_vigueur_et_la_revalorisation(session, contrat_avec_histoire) -> None:
    etat = etat_a_la_date(session, contrat_avec_histoire, date(2024, 7, 15))
    assert etat.statut is StatutContrat.EN_COURS
    assert etat.est_en_portefeuille is True
    assert etat.cotisation_mensuelle_cents == COTISATION_INITIALE
    assert etat.avenant_type == TypeAvenant.MISE_EN_VIGUEUR.value


def test_le_jour_meme_d_un_avenant_celui_ci_s_applique(session, contrat_avec_histoire) -> None:
    """La date d'effet est inclusive : un avenant au 1er janvier s'applique bien le 1er janvier."""
    veille = etat_a_la_date(session, contrat_avec_histoire, DATE_REVALORISATION - timedelta(days=1))
    jour = etat_a_la_date(session, contrat_avec_histoire, DATE_REVALORISATION)
    assert veille.cotisation_mensuelle_cents == COTISATION_INITIALE
    assert jour.cotisation_mensuelle_cents == COTISATION_REVALORISEE


def test_apres_la_resiliation_le_contrat_est_sorti(session, contrat_avec_histoire) -> None:
    etat = etat_a_la_date(session, contrat_avec_histoire, date(2026, 6, 1))
    assert etat.statut is StatutContrat.RESILIE
    assert etat.est_en_portefeuille is False
    assert etat.motif_resiliation is MotifResiliation.ECHEANCE


def test_un_contrat_suspendu_reste_au_portefeuille(session, contrat_oceane) -> None:
    """La garantie est suspendue, le contrat n'est pas sorti : il compte encore au portefeuille."""
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    service.suspend(session, contrat_oceane, date(2024, 9, 1))
    etat = etat_a_la_date(session, contrat_oceane, date(2024, 10, 1))
    assert etat.statut is StatutContrat.SUSPENDU
    assert etat.est_en_portefeuille is True


def test_deux_avenants_le_meme_jour_le_dernier_saisi_gagne(session, contrat_oceane) -> None:
    """Cas reel : une revalorisation au 1er janvier, puis un changement de formule demande pour ce meme
    1er janvier. C'est le dernier saisi qui vaut, donc le plus grand numero d'ordre."""
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.REVALORISATION_TARIFAIRE,
        date_effet=DATE_REVALORISATION,
        cotisation_mensuelle_cents=7_000,
    )
    formule_f3 = session.scalars(
        select(Formule).where(Formule.produit_id == contrat_oceane.produit_id, Formule.code == "F3")
    ).one()
    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.CHANGEMENT_FORMULE,
        date_effet=DATE_REVALORISATION,
        formule_id=formule_f3.id,
        cotisation_mensuelle_cents=9_900,
    )

    etat = etat_a_la_date(session, contrat_oceane, DATE_REVALORISATION)
    assert etat.cotisation_mensuelle_cents == 9_900
    assert etat.formule_id == formule_f3.id
    assert etat.avenant_type == TypeAvenant.CHANGEMENT_FORMULE.value


def test_l_avenant_en_vigueur_est_bien_le_dernier_anterieur(session, contrat_avec_histoire) -> None:
    avenant = avenant_en_vigueur(session, contrat_avec_histoire.id, date(2025, 6, 1))
    assert avenant is not None
    assert avenant.type_avenant is TypeAvenant.REVALORISATION_TARIFAIRE


def test_le_cache_du_contrat_egale_la_reconstitution(session, contrat_avec_histoire) -> None:
    """Les colonnes d'etat courant de `contrat` sont un cache du dernier avenant. Ce test le verifie par
    un chemin different de celui qui l'a ecrit : la reconstitution."""
    etat = etat_a_la_date(session, contrat_avec_histoire, DATE_OBSERVATION)
    assert etat.statut is contrat_avec_histoire.statut
    assert etat.formule_id == contrat_avec_histoire.formule_id
    assert etat.apporteur_id == contrat_avec_histoire.apporteur_id
    assert etat.cotisation_mensuelle_cents == contrat_avec_histoire.cotisation_mensuelle_cents
    assert etat.fractionnement is contrat_avec_histoire.fractionnement
    assert etat.motif_resiliation is contrat_avec_histoire.motif_resiliation


def test_les_numeros_d_ordre_sont_contigus_et_croissants(session, contrat_avec_histoire) -> None:
    ordres = [a.numero_ordre for a in contrat_avec_histoire.avenants]
    assert ordres == list(range(len(ordres)))


def test_les_dates_d_effet_sont_croissantes(session, contrat_avec_histoire) -> None:
    """Condition pour que la reconstitution soit non ambigue."""
    dates = [a.date_effet for a in contrat_avec_histoire.avenants]
    assert dates == sorted(dates)


def test_la_reconstitution_couvre_tout_le_portefeuille_genere(session) -> None:
    """Sur **chaque** contrat de la base, le cache doit egaler la reconstitution.

    Sans objet quand la base ne contient pas de portefeuille genere ; le test se declare alors saute,
    plutot que de passer en silence sur une boucle vide. Lance contre la base de demonstration, il
    parcourt les 5 777 contrats.

    Il n'y avait ici ni `skip` ni parcours complet : une limite a 200 contrats non ordonnes et une
    boucle vide par defaut. Les 40 contrats dont le cache divergeait de la reconstitution passaient
    donc inapercus, alors que ce test est precisement celui qui doit les attraper.
    """
    contrats = list(session.scalars(select(Contrat).order_by(Contrat.id)))
    if len(contrats) < 100:
        pytest.skip("base de test sans portefeuille genere")

    # Date fixe, et non `date.today()` : le resultat d'un test ne doit pas dependre du calendrier.
    for contrat in contrats:
        etat = etat_a_la_date(session, contrat, DATE_OBSERVATION)
        assert etat.statut is contrat.statut, contrat.numero_contrat
        assert etat.cotisation_mensuelle_cents == contrat.cotisation_mensuelle_cents, contrat.numero_contrat
        assert etat.apporteur_id == contrat.apporteur_id, contrat.numero_contrat
        assert etat.formule_id == contrat.formule_id, contrat.numero_contrat
        assert etat.fractionnement is contrat.fractionnement, contrat.numero_contrat


def test_les_dates_d_effet_croissent_avec_le_rang_sur_tout_le_portefeuille(session) -> None:
    """Un historique dont les dates reculent rendrait la reconstitution ambigue.

    La regle est appliquee par le service aux saisies ; ce test verifie qu'elle vaut aussi pour les
    donnees generees. Le generateur l'enfreignait sur 46 contrats.
    """
    from sqlalchemy import func

    nombre = session.scalar(select(func.count(Contrat.id))) or 0
    if nombre < 100:
        pytest.skip("base de test sans portefeuille genere")

    precedent = (
        select(Avenant.contrat_id, Avenant.numero_ordre, Avenant.date_effet).subquery()
    )
    suivant = (
        select(Avenant.contrat_id, Avenant.numero_ordre, Avenant.date_effet).subquery()
    )
    hors_ordre = session.scalar(
        select(func.count())
        .select_from(precedent)
        .join(
            suivant,
            (suivant.c.contrat_id == precedent.c.contrat_id)
            & (suivant.c.numero_ordre == precedent.c.numero_ordre + 1),
        )
        .where(suivant.c.date_effet < precedent.c.date_effet)
    )
    assert hors_ordre == 0, f"{hors_ordre} avenants reculent dans le temps"


def test_le_cache_egale_la_reconstitution_apres_changement_d_apporteur(session, contrat_oceane) -> None:
    """La reconstitution doit rendre l'ancien apporteur la veille, et le nouveau le jour meme.

    C'est la condition pour qu'un changement d'apporteur ne reecrive pas les bordereaux de
    retrocession deja regles, ce qui est la raison d'etre de toute la brique d'historisation.
    """
    from sqlalchemy import select as selectionne

    from courtage.modeles.referentiel import Apporteur

    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    ancien = contrat_oceane.apporteur_id
    nouveau = session.scalars(
        selectionne(Apporteur).where(Apporteur.id != ancien).order_by(Apporteur.code)
    ).first()
    bascule = date(2025, 4, 1)
    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.CHANGEMENT_APPORTEUR,
        date_effet=bascule,
        apporteur_id=nouveau.id,
    )

    veille = etat_a_la_date(session, contrat_oceane, bascule - timedelta(days=1))
    jour = etat_a_la_date(session, contrat_oceane, bascule)
    assert veille.apporteur_id == ancien
    assert jour.apporteur_id == nouveau.id


def test_un_avenant_resilie_porte_toujours_un_motif(session, contrat_avec_histoire) -> None:
    """La contrainte existe en base ; ce test verifie qu'elle est respectee par le chemin normal."""
    resiliations = [
        a for a in session.scalars(select(Avenant).where(Avenant.contrat_id == contrat_avec_histoire.id))
        if a.statut is StatutContrat.RESILIE
    ]
    assert resiliations
    assert all(a.motif_resiliation is not None for a in resiliations)


def test_le_contrat_reprend_la_cotisation_de_son_dernier_avenant(session, contrat_oceane) -> None:
    """Le report de l'avenant vers le cache du contrat doit porter **toutes** les valeurs.

    Trou signale par une verification par mutation : le report de la cotisation pouvait etre retire de
    `applique_avenant_au_contrat` sans qu'aucun test echoue. La liste du portefeuille et les appels de
    cotisation lisent cette colonne : une cotisation qui ne suit pas son avenant facture l'ancien
    tarif indefiniment.
    """
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    cotisation_initiale = contrat_oceane.cotisation_mensuelle_cents

    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.REVALORISATION_TARIFAIRE,
        date_effet=date(2025, 1, 1),
        cotisation_mensuelle_cents=cotisation_initiale + 1_234,
    )

    session.refresh(contrat_oceane)
    assert contrat_oceane.cotisation_mensuelle_cents == cotisation_initiale + 1_234


def test_le_contrat_reprend_la_formule_et_l_apporteur_de_son_dernier_avenant(
    session, contrat_oceane
) -> None:
    """Meme controle pour les deux autres valeurs que le cache porte."""
    from courtage.modeles.referentiel import Apporteur, Formule

    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    autre_formule = session.scalars(
        select(Formule).where(
            Formule.produit_id == contrat_oceane.produit_id,
            Formule.id != contrat_oceane.formule_id,
        )
    ).first()
    autre_apporteur = session.scalars(
        select(Apporteur).where(Apporteur.id != contrat_oceane.apporteur_id).order_by(Apporteur.code)
    ).first()

    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.CHANGEMENT_FORMULE,
        date_effet=date(2025, 2, 1),
        formule_id=autre_formule.id,
    )
    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.CHANGEMENT_APPORTEUR,
        date_effet=date(2025, 3, 1),
        apporteur_id=autre_apporteur.id,
    )

    session.refresh(contrat_oceane)
    assert contrat_oceane.formule_id == autre_formule.id
    assert contrat_oceane.apporteur_id == autre_apporteur.id
