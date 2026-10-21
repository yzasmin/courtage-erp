"""Commissions et retrocessions : le taux retenu, l'assiette, l'apporteur, et le bordereau mensuel.

Ces tests portent sur les trois affirmations qui engagent le cabinet devant une compagnie et devant ses
apporteurs, et qu'aucune relecture de code ne remplace :

1. **le taux applique est celui en vigueur a la date d'echeance**, pas le plus recent ;
2. **l'assiette suit le parametre de la table**, cotisation encaissee ou cotisation appelee ;
3. **l'apporteur retenu est celui en vigueur a la date d'echeance**, reconstitue par les avenants.

Et une quatrieme, qui est une exigence du graphe : le calcul est idempotent, de sorte qu'une relance
apres incident ne double pas les commissions du mois.
"""

from __future__ import annotations

from datetime import date, timedelta

from outils import PERIODE_TEST, depose_encaissements, ligne_encaissement
from sqlalchemy import func, select

from courtage.domaine.montants import applique_taux
from courtage.flux import bordereaux as module_bordereaux
from courtage.flux import commissions as module_commissions
from courtage.flux import ingestion
from courtage.flux.commissions import prorata_hors_taxe
from courtage.flux.rapprochement import rapproche
from courtage.modeles.enums import AssietteCommission, TypeBordereau
from courtage.modeles.financier import Bordereau, Commission, Retrocession
from courtage.modeles.portefeuille import Avenant
from courtage.modeles.referentiel import Apporteur, TauxCommission, TauxRetrocession


def encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane, montant=None):
    """Depose un releve qui regle le dernier appel, puis rapproche. Prealable a toute commission."""
    appel = appels_oceane[-1]
    depose_encaissements(
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                montant if montant is not None else appel.montant_total_cents,
                encaissement_oceane.date_encaissement,
                reference_appel=appel.reference_appel,
            )
        ],
    )
    ingestion.detecte(session)
    ingestion.archive(session)
    ingestion.charge(session)
    rapproche(session)
    return appel


def test_le_taux_retenu_est_celui_de_la_date_d_echeance(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit
):
    """Deux baremes successifs : l'echeance de juin 2026 applique le bareme entre en vigueur en juin.

    C'est la regle qui protege les bordereaux deja regles. Sans elle, une revalorisation du bareme
    reecrirait l'historique des commissions, ce qu'aucune compagnie n'accepte.
    """
    appel = encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane)
    resultat = module_commissions.calcule(session, periodes=[PERIODE_TEST])

    assert resultat.commissions_creees >= 1
    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    assert commission.taux_bp == taux_du_produit["nouveau_bp"]
    assert commission.assiette_cents == appel.montant_ht_cents
    assert commission.montant_cents == applique_taux(appel.montant_ht_cents, taux_du_produit["nouveau_bp"])


def test_une_echeance_anterieure_applique_l_ancien_bareme(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit
):
    """La meme chaine, sur une echeance d'avril 2026, applique le bareme en vigueur en avril."""
    appel = appels_oceane[0]
    depose_encaissements(
        espace_flux,
        [
            ligne_encaissement(
                encaissement_oceane.reference_bancaire,
                appel.montant_total_cents,
                appel.date_echeance + timedelta(days=3),
                reference_appel=appel.reference_appel,
            )
        ],
    )
    ingestion.detecte(session)
    ingestion.archive(session)
    ingestion.charge(session)
    rapproche(session)

    module_commissions.calcule(session, periodes=[date(2026, 4, 1)])
    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    assert commission.taux_bp == taux_du_produit["ancien_bp"]


def test_assiette_sur_cotisation_appelee(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit, contrat_en_vigueur
):
    """L'assiette suit le parametre de la table, et non une constante du code.

    Les deux pratiques coexistent dans le metier. Le projet retient la cotisation encaissee, la plus
    prudente, et doit savoir calculer l'autre sans modification de code : c'est ce que ce test verifie,
    en basculant le parametre et en constatant que l'assiette devient celle de l'appel, meme sans
    encaissement.
    """
    for taux in session.scalars(
        select(TauxCommission).where(TauxCommission.produit_id == contrat_en_vigueur.produit_id)
    ):
        taux.assiette = AssietteCommission.COTISATION_APPELEE
    session.flush()

    appel = appels_oceane[-1]
    resultat = module_commissions.calcule(session, periodes=[PERIODE_TEST])
    assert resultat.commissions_creees >= 1
    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    assert commission.assiette_cents == appel.montant_ht_cents, (
        "sur assiette appelee, la commission est due meme sans encaissement rapproche"
    )


def test_assiette_au_prorata_sur_reglement_partiel(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit
):
    """Un acompte regle la cotisation et la taxe dans la meme proportion."""
    appel = appels_oceane[-1]
    acompte = round(appel.montant_total_cents * 0.6)
    encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane, montant=acompte)
    module_commissions.calcule(session, periodes=[PERIODE_TEST])

    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    attendu = prorata_hors_taxe(acompte, appel.montant_ht_cents, appel.montant_total_cents)
    assert commission.assiette_cents == attendu
    assert commission.assiette_cents < appel.montant_ht_cents


def test_sans_encaissement_aucune_commission(
    session, espace_flux, appels_oceane, taux_du_produit
):
    """Sur assiette encaissee, un appel que personne n'a paye ne produit aucune commission.

    Et le motif est compte, non avale en silence : un bordereau vide dont personne ne comprend la cause
    est pire qu'une commission manquante.
    """
    appel = appels_oceane[-1]
    resultat = module_commissions.calcule(session, periodes=[PERIODE_TEST])
    # Le compte porte sur **cet** appel et non sur toute la base : la suite tourne aussi contre la
    # base de demonstration, qui contient deja des milliers de commissions legitimes.
    assert session.scalar(select(func.count(Commission.id)).where(Commission.appel_id == appel.id)) == 0
    assert resultat.ecartes["aucun_encaissement_rapproche"] >= 1


def test_la_compagnie_qui_encaisse_elle_meme_laisse_commissionner_sur_l_appele(
    session, espace_flux, appels_oceane, taux_du_produit
):
    """Encaissement non delegue : la commission existe, sur la cotisation appelee hors taxe.

    Contresens metier corrige. Ces appels etaient purement ecartes, et 31 pour cent du portefeuille,
    1 184 appels sur 3 776 dans le jeu de demonstration, disparaissaient des bordereaux de
    commissions. Or un courtier dont la compagnie encaisse directement est commissionne quand meme :
    la compagnie encaisse, calcule la commission due et la verse avec son bordereau de commissions.

    Le test retire l'acte d'encaissement de la convention de delegation du produit, sans toucher au
    reste, et exige une commission assise sur la cotisation appelee hors taxe, plus un compteur de
    repli renseigne pour que la ligne soit rapprochable du bordereau de la compagnie.
    """
    from courtage.modeles.delegation import ActeDelegue, ConventionDelegation, ConventionProduit
    from courtage.modeles.enums import ActeGestion
    from courtage.modeles.portefeuille import Contrat

    appel = appels_oceane[-1]
    produit_id = session.get(Contrat, appel.contrat_id).produit_id
    conventions = session.scalars(
        select(ConventionDelegation.id)
        .join(ConventionProduit, ConventionProduit.convention_id == ConventionDelegation.id)
        .where(ConventionProduit.produit_id == produit_id)
    ).all()
    assert conventions, "le produit du contrat de test doit etre couvert par une convention"
    retires = session.scalars(
        select(ActeDelegue).where(
            ActeDelegue.convention_id.in_(conventions),
            ActeDelegue.acte == ActeGestion.ENCAISSEMENT,
        )
    ).all()
    assert retires, "l'encaissement doit etre delegue au depart, sinon le test ne prouve rien"
    for acte in retires:
        session.delete(acte)
    session.flush()

    resultat = module_commissions.calcule(session, periodes=[PERIODE_TEST])

    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    assert commission.assiette_cents == appel.montant_ht_cents, (
        "sans delegation de l'encaissement, l'assiette est la cotisation appelee hors taxe"
    )
    assert commission.montant_cents > 0
    assert resultat.assiettes_de_repli["assiette_appelee_car_encaissement_non_delegue"] >= 1, (
        "le repli doit etre compte : ces lignes sont celles a rapprocher du bordereau de commissions"
        " recu de la compagnie"
    )
    assert "encaissement_non_delegue_assiette_inconnue" not in resultat.ecartes, (
        "plus aucun appel ne doit etre ecarte au motif que la compagnie encaisse elle-meme"
    )


def test_le_trop_percu_n_est_pas_commissionnable(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit
):
    """L'assiette est plafonnee a l'appel : commissionner un trop percu serait indefendable."""
    appel = appels_oceane[-1]
    encaisse_le_dernier_appel(
        session, espace_flux, appels_oceane, encaissement_oceane, montant=appel.montant_total_cents + 5_000
    )
    module_commissions.calcule(session, periodes=[PERIODE_TEST])

    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    assert commission.assiette_cents == appel.montant_ht_cents


def test_apporteur_retenu_a_la_date_d_echeance(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit, contrat_en_vigueur
):
    """Un changement d'apporteur posterieur a l'echeance ne redonne pas la commission a l'arrivant.

    Un avenant de changement d'apporteur est saisi avec effet au mois suivant l'echeance. La
    retrocession de l'echeance doit rester a l'apporteur d'origine.
    """
    arrivant = session.scalars(
        select(Apporteur).where(Apporteur.id != contrat_en_vigueur.apporteur_id).order_by(Apporteur.code)
    ).first()
    assert arrivant is not None
    session.add(
        TauxRetrocession(
            apporteur_id=arrivant.id,
            produit_id=None,
            taux_bp=7_000,
            date_debut_validite=date(2024, 1, 1),
            date_fin_validite=None,
        )
    )
    dernier_ordre = (
        session.scalar(select(func.max(Avenant.numero_ordre)).where(Avenant.contrat_id == contrat_en_vigueur.id))
        or 0
    )
    session.add(
        Avenant(
            contrat_id=contrat_en_vigueur.id,
            numero_ordre=dernier_ordre + 1,
            type_avenant="changement_apporteur",
            date_effet=date(2026, 7, 1),
            date_saisie=date(2026, 6, 20),
            auteur="test",
            statut=contrat_en_vigueur.statut,
            formule_id=contrat_en_vigueur.formule_id,
            apporteur_id=arrivant.id,
            cotisation_mensuelle_cents=contrat_en_vigueur.cotisation_mensuelle_cents,
            fractionnement=contrat_en_vigueur.fractionnement,
            motif_resiliation=None,
        )
    )
    session.flush()

    appel = encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane)
    module_commissions.calcule(session, periodes=[PERIODE_TEST])

    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    retrocession = session.scalars(
        select(Retrocession).where(Retrocession.commission_id == commission.id)
    ).one()
    assert retrocession.apporteur_id == contrat_en_vigueur.apporteur_id, (
        "l'echeance de juin revient a l'apporteur en vigueur en juin, pas a celui de juillet"
    )
    assert retrocession.taux_bp == taux_du_produit["retrocession_bp"]
    assert retrocession.montant_cents == applique_taux(
        commission.montant_cents, taux_du_produit["retrocession_bp"]
    )
    assert retrocession.montant_cents <= commission.montant_cents


def test_calcul_idempotent(session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit):
    """Rejouer le calcul ne cree rien et ne modifie rien : la relance apres incident est sans risque."""
    appel = encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane)
    premier = module_commissions.calcule(session, periodes=[PERIODE_TEST])
    second = module_commissions.calcule(session, periodes=[PERIODE_TEST])

    # Les comptes sont relatifs, et non absolus : la suite tourne aussi contre la base de
    # demonstration, ou des milliers de commissions legitimes existent deja. Ce qui prouve
    # l'idempotence, c'est que le second passage ne cree ni ne modifie rien, et que le nombre de
    # lignes inchangees egale exactement le nombre de lignes que le premier avait creees.
    assert premier.commissions_creees >= 1
    assert second.commissions_creees == 0
    assert second.commissions_mises_a_jour == 0
    assert second.commissions_inchangees == premier.commissions_creees
    assert second.montant_commissions_cents == premier.montant_commissions_cents
    assert session.scalar(select(func.count(Commission.id)).where(Commission.appel_id == appel.id)) == 1
    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    assert (
        session.scalar(
            select(func.count(Retrocession.id)).where(Retrocession.commission_id == commission.id)
        )
        == 1
    )


def test_une_commission_par_appel(session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit):
    """L'unicite est portee par la base : le double commissionnement est l'erreur la plus couteuse."""
    appel = encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane)
    module_commissions.calcule(session, periodes=[PERIODE_TEST])
    assert (
        session.scalar(select(func.count(Commission.id)).where(Commission.appel_id == appel.id)) == 1
    )


def test_bordereaux_mensuels_et_leurs_totaux(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit, contrat_en_vigueur
):
    """Un bordereau de commissions par compagnie et un bordereau de retrocessions par apporteur, dont
    le total tombe juste."""
    appel = encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane)
    module_commissions.calcule(session, periodes=[PERIODE_TEST])
    resultat = module_bordereaux.produit(session, periodes=[PERIODE_TEST])

    assert resultat.bordereaux_commissions >= 1
    assert resultat.bordereaux_retrocessions >= 1

    # La commission de **cet** appel, et la retrocession qui en decoule. Les comptes absolus ne
    # tiendraient pas sur la base de demonstration, ou la suite est aussi rejouee.
    commission = session.scalars(select(Commission).where(Commission.appel_id == appel.id)).one()
    retrocession = session.scalars(
        select(Retrocession).where(Retrocession.commission_id == commission.id)
    ).one()

    bordereau_commissions = session.get(Bordereau, commission.bordereau_id)
    assert bordereau_commissions is not None
    assert bordereau_commissions.type_bordereau is TypeBordereau.COMMISSIONS
    assert bordereau_commissions.compagnie_id is not None
    assert bordereau_commissions.apporteur_id is None

    bordereau_retrocessions = session.get(Bordereau, retrocession.bordereau_id)
    assert bordereau_retrocessions is not None
    assert bordereau_retrocessions.type_bordereau is TypeBordereau.RETROCESSIONS
    assert bordereau_retrocessions.apporteur_id == contrat_en_vigueur.apporteur_id
    assert bordereau_retrocessions.compagnie_id is None

    # Le total de chaque bordereau egale la somme de ses propres lignes, ce qui est la seule
    # affirmation verifiable quel que soit le contenu de la base.
    somme_commissions = session.scalar(
        select(func.coalesce(func.sum(Commission.montant_cents), 0)).where(
            Commission.bordereau_id == bordereau_commissions.id
        )
    )
    assert bordereau_commissions.montant_total_cents == somme_commissions
    somme_retrocessions = session.scalar(
        select(func.coalesce(func.sum(Retrocession.montant_cents), 0)).where(
            Retrocession.bordereau_id == bordereau_retrocessions.id
        )
    )
    assert bordereau_retrocessions.montant_total_cents == somme_retrocessions

    # Chaque fichier ecrit porte une ligne de total conforme a son nombre de lignes.
    from pathlib import Path as Chemin

    assert resultat.fichiers
    for chemin in resultat.fichiers:
        lignes = Chemin(chemin).read_text(encoding="utf-8-sig").splitlines()
        assert lignes[-1].startswith(f"TOTAL;{len(lignes) - 2};")


def test_production_des_bordereaux_idempotente(
    session, espace_flux, appels_oceane, encaissement_oceane, taux_du_produit
):
    """Rejouer la production reecrit les memes fichiers et ne cree aucun doublon en base."""
    encaisse_le_dernier_appel(session, espace_flux, appels_oceane, encaissement_oceane)
    module_commissions.calcule(session, periodes=[PERIODE_TEST])
    premier = module_bordereaux.produit(session, periodes=[PERIODE_TEST])
    second = module_bordereaux.produit(session, periodes=[PERIODE_TEST])

    assert premier.crees >= 2
    assert second.crees == 0
    assert second.mis_a_jour == 0
    assert second.inchanges == premier.crees
    assert (session.scalar(select(func.count(Bordereau.id))) or 0) == premier.crees
