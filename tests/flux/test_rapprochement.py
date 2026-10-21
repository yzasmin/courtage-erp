"""Rapprochement : par reference, puis par montant et date, et les quatre statuts de la specification.

Un test par chemin, parce que les deux methodes n'ont pas la meme valeur de preuve. La correspondance
par reference est une certitude : le payeur a repris la reference de sa quittance. La correspondance par
montant et date est une presomption, et un gestionnaire qui instruit un litige doit savoir laquelle des
deux il relit. C'est pourquoi la methode employee est conservee ligne a ligne, et pourquoi elle est
testee.
"""

from __future__ import annotations

from datetime import timedelta

from outils import depose_encaissements, ligne_encaissement
from sqlalchemy import select

from courtage.flux import ingestion
from courtage.flux.enums import MethodeRapprochement
from courtage.flux.modeles import RapprochementLigne
from courtage.flux.rapprochement import rapproche
from courtage.modeles.delegation import ActeDelegue, ConventionDelegation, ConventionProduit
from courtage.modeles.enums import ActeGestion, StatutRapprochement
from courtage.modeles.financier import Encaissement
from courtage.modeles.referentiel import Produit


def charge_le_releve(session, espace_flux, lignes):
    depose_encaissements(espace_flux, lignes)
    ingestion.detecte(session)
    ingestion.archive(session)
    return ingestion.charge(session)


def verdict(session, reference_bancaire: str) -> RapprochementLigne:
    ligne = session.scalars(
        select(RapprochementLigne).where(RapprochementLigne.reference_bancaire == reference_bancaire)
    ).first()
    assert ligne is not None, f"aucun verdict de rapprochement pour {reference_bancaire}"
    return ligne


def test_rapprochement_par_reference(session, espace_flux, appels_oceane, encaissement_oceane):
    """Le payeur a repris la reference de sa quittance : correspondance immediate et certaine."""
    appel = appels_oceane[-1]
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                encaissement_oceane.date_encaissement,
                reference_appel=appel.reference_appel,
            )
        ],
    )
    resultat = rapproche(session)

    ligne = verdict(session, encaissement_oceane.reference_bancaire)
    assert ligne.methode is MethodeRapprochement.REFERENCE
    assert ligne.statut == StatutRapprochement.RAPPROCHE.value
    assert ligne.appel_id == appel.id
    assert ligne.ecart_cents == 0
    assert ligne.fenetre_jours is None, (
        "la fenetre de tolerance n'a pas servi : la conserver laisserait croire a une presomption"
    )
    assert resultat.par_methode["reference"] == 1

    # Le coeur ERP est mis a jour, pour que l'ecran des anomalies lise une seule verite.
    mouvement = session.get(Encaissement, encaissement_oceane.id)
    assert mouvement.statut_rapprochement is StatutRapprochement.RAPPROCHE
    assert mouvement.appel_id == appel.id


def test_rapprochement_par_montant_et_date(session, espace_flux, appels_oceane, encaissement_oceane):
    """Virement saisi a la main, sans reference : c'est le montant et la date qui designent l'appel."""
    appel = appels_oceane[-1]
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                appel.date_echeance + timedelta(days=4),
                reference_appel=None,
                numero_contrat=appel.contrat.numero_contrat,
            )
        ],
    )
    rapproche(session)

    ligne = verdict(session, encaissement_oceane.reference_bancaire)
    assert ligne.methode is MethodeRapprochement.MONTANT_DATE
    assert ligne.statut == StatutRapprochement.RAPPROCHE.value
    assert ligne.appel_id == appel.id
    assert ligne.fenetre_jours == 15, (
        "la fenetre employee est conservee : un rapprochement par montant et date depend d'un"
        " parametre, et le relire des mois plus tard demande de savoir lequel"
    )


def test_hors_fenetre_le_rapprochement_echoue(session, espace_flux, appels_oceane, encaissement_oceane):
    """Hors de la fenetre, le montant seul ne suffit pas : trois echeances identiques se ressemblent."""
    appel = appels_oceane[-1]
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                appel.date_echeance + timedelta(days=120),
                reference_appel=None,
                numero_contrat=appel.contrat.numero_contrat,
            )
        ],
    )
    rapproche(session, fenetre_jours=5)

    ligne = verdict(session, encaissement_oceane.reference_bancaire)
    assert ligne.statut == StatutRapprochement.NON_TROUVE.value
    assert ligne.methode is MethodeRapprochement.AUCUNE
    assert ligne.appel_id is None


def test_un_appel_detache_de_sa_recette_redevient_attendu(
    session, espace_flux, appels_oceane, encaissement_oceane
):
    """Detacher un mouvement d'un appel doit aussi revenir sur le statut de cet appel.

    Defaut constate en executant la chaine complete puis le controle de coherence : onze appels se
    declaraient encaisses ou partiels alors qu'aucun encaissement ne pointait plus sur eux. Le
    rapprochement detachait bien le mouvement dont il ne retrouvait pas la correspondance, mais il
    laissait a l'appel le statut que le quittancement lui avait donne. L'ecran des anomalies et les
    marts lisaient alors deux verites contradictoires sur la meme ligne.

    Le statut redevient `attendu` et non `impaye` : l'impaye est un constat de gestion, qui suppose une
    echeance passee et une relance. Ici le cabinet constate seulement qu'il n'a rien a rattacher.
    """
    from courtage.modeles.enums import StatutAppel

    appel = appels_oceane[-1]
    # Point de depart : l'appel est encaisse et la recette lui est rattachee, comme apres un
    # quittancement suivi d'un encaissement connu du coeur ERP.
    encaissement_oceane.appel_id = appel.id
    encaissement_oceane.statut_rapprochement = StatutRapprochement.RAPPROCHE
    appel.statut = StatutAppel.ENCAISSE
    session.flush()

    # Le releve arrive avec le meme mouvement, mais a une date qui le place hors de toute fenetre et
    # sans reference de quittance : le rapprochement ne retrouve plus son appel.
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                appel.date_echeance + timedelta(days=120),
                reference_appel=None,
                numero_contrat=appel.contrat.numero_contrat,
            )
        ],
    )
    resultat = rapproche(session, fenetre_jours=5)

    assert encaissement_oceane.appel_id is None, "le mouvement doit etre detache de son appel"
    assert appel.statut is StatutAppel.ATTENDU, (
        "un appel que plus aucune recette ne solde ne peut pas rester encaisse"
    )
    assert resultat.appels_reexamines >= 1, (
        "le compte rendu doit dire combien d'appels ont vu leur statut rededuit"
    )


def test_la_fenetre_est_parametrable(session, espace_flux, appels_oceane, encaissement_oceane):
    """Le meme mouvement se rapproche ou non selon la fenetre. La specification exige ce parametre."""
    appel = appels_oceane[-1]
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                appel.date_echeance + timedelta(days=20),
                reference_appel=None,
                numero_contrat=appel.contrat.numero_contrat,
            )
        ],
    )
    rapproche(session, fenetre_jours=5)
    assert verdict(session, encaissement_oceane.reference_bancaire).statut == "non_trouve"

    rapproche(session, fenetre_jours=30)
    ligne = verdict(session, encaissement_oceane.reference_bancaire)
    assert ligne.statut == StatutRapprochement.RAPPROCHE.value
    assert ligne.fenetre_jours == 30


def test_reglement_partiel(session, espace_flux, appels_oceane, encaissement_oceane):
    """Un acompte au-dessus de la part minimale reste un reglement partiel du meme appel."""
    appel = appels_oceane[-1]
    acompte = round(appel.montant_total_cents * 0.6)
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                acompte,
                encaissement_oceane.date_encaissement,
                reference_appel=appel.reference_appel,
            )
        ],
    )
    rapproche(session)

    ligne = verdict(session, encaissement_oceane.reference_bancaire)
    assert ligne.statut == StatutRapprochement.PARTIEL.value
    assert ligne.ecart_cents == acompte - appel.montant_total_cents


def test_trop_percu_donne_un_ecart(session, espace_flux, appels_oceane, encaissement_oceane):
    """Un versement superieur a l'appel n'est pas un reglement : c'est un ecart a instruire."""
    appel = appels_oceane[-1]
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents + 1_500,
                encaissement_oceane.date_encaissement,
                reference_appel=appel.reference_appel,
            )
        ],
    )
    rapproche(session)
    assert verdict(session, encaissement_oceane.reference_bancaire).statut == StatutRapprochement.ECART.value


def test_versement_trop_faible_donne_un_ecart(session, espace_flux, appels_oceane, encaissement_oceane):
    """En dessous de la part minimale, ce n'est plus un acompte mais une autre operation."""
    appel = appels_oceane[-1]
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                round(appel.montant_total_cents * 0.1),
                encaissement_oceane.date_encaissement,
                reference_appel=appel.reference_appel,
            )
        ],
    )
    rapproche(session)
    assert verdict(session, encaissement_oceane.reference_bancaire).statut == StatutRapprochement.ECART.value


def test_mouvement_inconnu_du_coeur_erp(session, espace_flux, appels_oceane):
    """Un credit que le cabinet n'a pas enregistre reste visible, sans creer d'encaissement d'office.

    Creer l'encaissement serait un acte de gestion que personne n'a demande, et qui echapperait au
    controle de delegation. Le verdict est donc enregistre sans `encaissement_id`, et le mouvement
    apparait dans le mart des mouvements non rapproches.
    """
    charge_le_releve(
        session,
        espace_flux,
        [ligne_encaissement("ENC-INCONNU-001", 4_200, appels_oceane[-1].date_echeance)],
    )
    resultat = rapproche(session)

    ligne = verdict(session, "ENC-INCONNU-001")
    assert ligne.encaissement_id is None
    assert ligne.statut == StatutRapprochement.NON_TROUVE.value
    assert resultat.mouvements_inconnus_erp == 1


def test_acte_non_delegue_nest_pas_rapproche(
    session, espace_flux, appels_oceane, encaissement_oceane, contrat_en_vigueur
):
    """Un acte non delegue ne se traite pas, meme si le fichier le contient et qu'un appel correspond.

    La compagnie preleve elle-meme : le cabinet n'encaisse pas pour elle. Prononcer un rapprochement
    reviendrait a enregistrer un acte qu'il n'a pas le droit d'accomplir. La ligne est comptee a part et
    figure au journal, et aucun verdict n'est ecrit.
    """
    appel = appels_oceane[-1]
    produit = session.get(Produit, contrat_en_vigueur.produit_id)
    conventions = list(
        session.scalars(
            select(ConventionDelegation)
            .join(ConventionProduit, ConventionProduit.convention_id == ConventionDelegation.id)
            .where(ConventionProduit.produit_id == produit.id)
        )
    )
    assert conventions, "le produit du contrat de reference doit etre couvert par une convention"
    for convention in conventions:
        for acte in list(
            session.scalars(
                select(ActeDelegue).where(
                    ActeDelegue.convention_id == convention.id,
                    ActeDelegue.acte == ActeGestion.ENCAISSEMENT,
                )
            )
        ):
            session.delete(acte)
    session.flush()

    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                encaissement_oceane.date_encaissement,
                reference_appel=appel.reference_appel,
            )
        ],
    )
    resultat = rapproche(session)

    assert resultat.actes_non_delegues == 1
    assert resultat.par_statut == {}, "aucun verdict ne doit etre prononce sur un acte non delegue"
    assert (
        session.scalars(
            select(RapprochementLigne).where(
                RapprochementLigne.reference_bancaire == encaissement_oceane.reference_bancaire
            )
        ).first()
        is None
    )


def test_rapprochement_idempotent(session, espace_flux, appels_oceane, encaissement_oceane):
    """Rejouer le rapprochement sur les memes lots recalcule les memes verdicts, sans en ajouter."""
    appel = appels_oceane[-1]
    charge_le_releve(
        session,
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                encaissement_oceane.date_encaissement,
                reference_appel=appel.reference_appel,
            )
        ],
    )
    premier = rapproche(session)
    identifiant = verdict(session, encaissement_oceane.reference_bancaire).id
    second = rapproche(session)

    # `appels_reexamines` compte les statuts d'appel **modifies**, pas les lignes examinees. Le
    # premier passage rattache le mouvement a son appel et change donc un statut ; le second ne
    # change plus rien. Exiger l'egalite de ce compteur reviendrait a exiger que le premier passage
    # ne serve a rien. Le comparer a zero au second passage est au contraire une preuve de plus :
    # c'est la definition meme de l'idempotence, lue dans le compte rendu.
    attendu = premier.en_dictionnaire()
    obtenu = second.en_dictionnaire()
    assert obtenu["appels_reexamines"] == 0, (
        "un second passage sur les memes lots ne doit plus modifier aucun statut d'appel"
    )
    attendu.pop("appels_reexamines")
    obtenu.pop("appels_reexamines")
    assert obtenu == attendu
    assert verdict(session, encaissement_oceane.reference_bancaire).id == identifiant, (
        "le verdict est mis a jour en place et non duplique"
    )
    assert len(list(session.scalars(select(RapprochementLigne)))) == 1
