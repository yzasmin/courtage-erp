"""Un test par controle bloquant, chacun prouvant le rejet du lot entier sans ecriture partielle.

La forme de ces tests est toujours la meme, et c'est voulu : compter les lignes de la couche brute,
deposer un bordereau porteur d'une seule anomalie, lancer le chargement, verifier que le lot est rejete
et que le compte de lignes **n'a pas bouge**. C'est la preuve que la specification demande, et elle ne
vaut que si elle est faite sur le compte reel des lignes et non sur le compteur du journal, qui pourrait
mentir.

Le huitieme controle, l'acte non delegue, ne figure pas dans la liste de la specification. Il est
pourtant le plus caracteristique du metier vise : une convention de delegation echue retire au cabinet
le droit de quittancer, et un bordereau qui continue d'arriver ne doit pas etre charge.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from outils import (
    PERIODE_TEST,
    depose_cotisations,
    ligne_cotisation,
)
from sqlalchemy import func, select

from courtage.flux import ingestion
from courtage.flux.enums import CodeAnomalie, StatutLot
from courtage.flux.fichiers import empreinte_fichier
from courtage.flux.modeles import AnomalieLot, BrutCotisation, BrutEncaissement, BrutPrestation, LotFichier
from courtage.modeles.delegation import ConventionDelegation, ConventionProduit
from courtage.modeles.enums import ActeGestion
from courtage.modeles.referentiel import Produit


def compte_lignes_brutes(session) -> int:
    """Nombre total de lignes presentes dans les trois tables de la couche brute."""
    total = 0
    for entite in (BrutCotisation, BrutEncaissement, BrutPrestation):
        total += session.scalar(select(func.count(entite.id))) or 0
    return total


def lance_la_chaine(session):
    """Detection, archivage, chargement. Les trois taches d'ingestion du graphe, dans l'ordre."""
    ingestion.detecte(session)
    ingestion.archive(session)
    return ingestion.charge(session)


def lot_unique(session) -> LotFichier:
    lots = list(session.scalars(select(LotFichier)))
    assert len(lots) == 1, f"un seul lot attendu, {len(lots)} trouves"
    return lots[0]


def codes_bloquants(session, lot: LotFichier) -> set[str]:
    return {
        code.value
        for code in session.scalars(
            select(AnomalieLot.code).where(
                AnomalieLot.lot_id == lot.id, AnomalieLot.severite == "bloquant"
            )
        )
    }


def verifie_rejet_integral(session, code_attendu: CodeAnomalie, lignes_avant: int) -> LotFichier:
    """Verifie qu'un lot a ete rejete pour le bon motif, **et pour celui-la seulement**.

    L'egalite stricte sur l'ensemble des codes bloquants n'est pas un exces de zele. Chaque test
    n'injecte qu'une anomalie : si un second controle se declenche, c'est que l'injection en a produit
    une autre sans le vouloir, et le test passerait pour une mauvaise raison. C'est exactement ainsi
    qu'un contrat sans date d'effet a ete pris pour une periode incoherente pendant une demi-journee.
    """
    lot = lot_unique(session)
    assert lot.statut is StatutLot.REJETE, f"lot {lot.reference_lot} non rejete : {lot.statut}"
    assert lot.motif_rejet, "un lot rejete porte toujours son motif"
    assert codes_bloquants(session, lot) == {code_attendu.value}, (
        f"un seul motif de rejet attendu, {code_attendu.value}, trouve"
        f" {sorted(codes_bloquants(session, lot))}"
    )
    assert lot.nombre_lignes_chargees == 0
    assert compte_lignes_brutes(session) == lignes_avant, (
        "ecriture partielle : des lignes de la couche brute ont survecu au rejet du lot"
    )
    return lot


@pytest.fixture
def lignes_conformes(session, contrat_en_vigueur, adherent, appels_oceane):
    """Trois lignes de bordereau conformes, derivees des appels reellement enregistres."""
    produit = session.get(Produit, contrat_en_vigueur.produit_id)
    return [
        ligne_cotisation(appel, contrat_en_vigueur.numero_contrat, adherent.numero_adherent, produit.code)
        for appel in appels_oceane
    ]


def test_un_bordereau_conforme_est_charge(session, espace_flux, lignes_conformes):
    """Temoin. Sans ce test, les suivants prouveraient seulement que tout est toujours rejete."""
    lignes_avant = compte_lignes_brutes(session)
    depose_cotisations(espace_flux, lignes_conformes)
    compte_rendu = lance_la_chaine(session)

    lot = lot_unique(session)
    assert lot.statut is StatutLot.CHARGE
    assert lot.motif_rejet is None
    assert lot.nombre_lignes_chargees == 3
    assert compte_lignes_brutes(session) == lignes_avant + 3
    assert compte_rendu.rejetes == 0


def test_schema_invalide_rejette_le_lot(session, espace_flux, lignes_conformes):
    """Une date impossible rend la ligne illisible, donc le bordereau non rapprochable."""
    lignes_avant = compte_lignes_brutes(session)
    lignes_conformes[1]["date_echeance"] = "31/02/2026"
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    verifie_rejet_integral(session, CodeAnomalie.SCHEMA_INVALIDE, lignes_avant)


def test_montant_non_numerique_rejette_le_lot(session, espace_flux, lignes_conformes):
    """Un montant qu'aucune conversion ne lit : la cellule d'un tableur dont la formule a echoue."""
    lignes_avant = compte_lignes_brutes(session)
    lignes_conformes[0]["montant_total"] = "#N/A"
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    # L'egalite stricte de `verifie_rejet_integral` porte ici tout le poids du test : le controle du
    # total doit se taire quand une ligne est illisible, sinon il fabriquerait une seconde anomalie a
    # partir de la premiere, et le rapport renvoye a l'emetteur l'enverrait sur une fausse piste.
    verifie_rejet_integral(session, CodeAnomalie.SCHEMA_INVALIDE, lignes_avant)


def test_doublon_de_cle_metier_rejette_le_lot(session, espace_flux, lignes_conformes):
    """Deux lignes pour une meme quittance : on ne sait pas laquelle est la bonne."""
    lignes_avant = compte_lignes_brutes(session)
    lignes_conformes[2]["reference_appel"] = lignes_conformes[0]["reference_appel"]
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    verifie_rejet_integral(session, CodeAnomalie.DOUBLON_CLE_METIER, lignes_avant)


def test_contrat_inconnu_rejette_le_lot(session, espace_flux, lignes_conformes):
    """La compagnie quittance un contrat que le cabinet ne gere pas : defaut de perimetre."""
    lignes_avant = compte_lignes_brutes(session)
    lignes_conformes[1]["numero_contrat"] = "CT-2026-099999"
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    verifie_rejet_integral(session, CodeAnomalie.CONTRAT_INCONNU, lignes_avant)


def test_adherent_inconnu_rejette_le_lot(session, espace_flux, lignes_conformes):
    lignes_avant = compte_lignes_brutes(session)
    lignes_conformes[0]["numero_adherent"] = "A9990001"
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    verifie_rejet_integral(session, CodeAnomalie.ADHERENT_INCONNU, lignes_avant)


def test_total_incoherent_rejette_le_lot(session, espace_flux, lignes_conformes):
    """Le fichier est tronque ou altere : aucune de ses lignes n'est fiable."""
    lignes_avant = compte_lignes_brutes(session)
    somme = sum(int(ligne["montant_total"]) for ligne in lignes_conformes)
    depose_cotisations(espace_flux, lignes_conformes, totaux_forces={"montant_total": somme + 1_250})
    lance_la_chaine(session)
    lot = verifie_rejet_integral(session, CodeAnomalie.TOTAL_INCOHERENT, lignes_avant)
    assert lot.montant_total_declare_cents == somme + 1_250
    assert lot.montant_total_calcule_cents == somme, (
        "le total declare et le total calcule sont tous deux conserves : l'ecart doit rester lisible"
        " apres coup, c'est la piece renvoyee a la compagnie"
    )


def test_periode_incoherente_rejette_le_lot(
    session, espace_flux, lignes_conformes, contrat_en_vigueur
):
    """Quittancer une periode anterieure a la date d'effet expose le cabinet."""
    lignes_avant = compte_lignes_brutes(session)
    avant_effet = contrat_en_vigueur.date_effet - timedelta(days=60)
    lignes_conformes[0]["periode_debut"] = avant_effet
    lignes_conformes[0]["periode_fin"] = avant_effet + timedelta(days=29)
    lignes_conformes[0]["date_echeance"] = avant_effet
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    verifie_rejet_integral(session, CodeAnomalie.PERIODE_INCOHERENTE, lignes_avant)


def test_periode_commencant_le_jour_de_la_resiliation_rejette_le_lot(
    session, espace_flux, lignes_conformes, contrat_en_vigueur
):
    """La frontiere exacte : une periode qui **commence** le jour de la resiliation n'est plus couverte.

    Ce test comble un trou trouve par mutation : remplacer `debut >= date_resiliation` par
    `debut > date_resiliation` dans `flux.controles` laissait toute la suite verte. Autrement dit, le
    controle etait bien ecrit mais personne ne verifiait sa borne, et un bordereau quittancant le mois
    qui commence le jour de la sortie passait sans bruit.

    Pourquoi la borne est stricte du cote de la resiliation et large du cote de la date d'effet. Une
    resiliation prononcee au 1er juin signifie que le contrat n'est plus garanti **a partir** du
    1er juin : la journee du 1er juin n'est pas couverte. Une date d'effet au 1er mars, elle, couvre le
    1er mars. Les deux conventions sont celles du metier, et elles sont volontairement dissymetriques.
    """
    from courtage.modeles.enums import MotifResiliation
    from courtage.services.contrats import resilie

    # La derniere des trois lignes conformes porte la periode du 1er au 30 juin 2026.
    derniere = lignes_conformes[-1]
    assert derniere["periode_debut"] == PERIODE_TEST, (
        "ce test suppose que la derniere ligne conforme ouvre la periode au premier du mois teste"
    )
    resilie(
        session,
        contrat_en_vigueur,
        date_effet=PERIODE_TEST,
        motif=MotifResiliation.INFRA_ANNUELLE,
        commentaire="Resiliation prononcee au premier jour de la periode quittancee",
    )
    session.flush()

    lignes_avant = compte_lignes_brutes(session)
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    lot = verifie_rejet_integral(session, CodeAnomalie.PERIODE_INCOHERENTE, lignes_avant)
    assert any(
        str(PERIODE_TEST) in (anomalie.valeur_constatee or "")
        for anomalie in session.scalars(
            select(AnomalieLot).where(AnomalieLot.lot_id == lot.id)
        )
    ), "l'anomalie doit designer la periode fautive, pas seulement le lot"


def test_fichier_deja_charge_rejette_le_second_depot(session, espace_flux, lignes_conformes):
    """Le meme contenu sous un autre nom : charger deux fois doublerait cotisations et commissions."""
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    lignes_apres_premier = compte_lignes_brutes(session)

    # La compagnie renvoie son bordereau renomme. Memes octets, autre nom.
    original = next((espace_flux / "archive").rglob("COTISATIONS_OCE_*.csv"))
    copie = espace_flux / "arrivee" / "COTISATIONS_OCE_202606_copie.csv"
    copie.write_bytes(original.read_bytes())

    lance_la_chaine(session)
    lots = {lot.nom_fichier: lot for lot in session.scalars(select(LotFichier))}
    assert len(lots) == 2
    copie_lot = lots["COTISATIONS_OCE_202606_copie.csv"]
    assert copie_lot.statut is StatutLot.REJETE
    assert CodeAnomalie.FICHIER_DEJA_CHARGE.value in codes_bloquants(session, copie_lot)
    assert compte_lignes_brutes(session) == lignes_apres_premier, (
        "le second depot ne doit ajouter aucune ligne"
    )


def test_acte_non_delegue_rejette_le_lot(session, espace_flux, lignes_conformes, contrat_en_vigueur):
    """Convention echue : le cabinet n'a plus le droit de quittancer, meme si le bordereau arrive.

    La convention du produit est close la veille de l'echeance du bordereau. Rien d'autre ne change :
    le contrat existe, les montants sont coherents, la periode est dans la garantie. Le seul motif de
    rejet possible est donc le refus d'acte.
    """
    lignes_avant = compte_lignes_brutes(session)
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
        convention.date_fin_validite = PERIODE_TEST - timedelta(days=1)
    session.flush()

    depose_cotisations(espace_flux, [lignes_conformes[-1]])
    lance_la_chaine(session)
    lot = verifie_rejet_integral(session, CodeAnomalie.ACTE_NON_DELEGUE, lignes_avant)
    anomalie = session.scalars(
        select(AnomalieLot).where(
            AnomalieLot.lot_id == lot.id, AnomalieLot.code == CodeAnomalie.ACTE_NON_DELEGUE
        )
    ).first()
    assert ActeGestion.QUITTANCEMENT.value in anomalie.message


def test_un_lot_fautif_ne_bloque_pas_les_autres(session, espace_flux, lignes_conformes):
    """Un lot, une transaction. Un cabinet ne bloque pas son mois parce qu'une compagnie a mal exporte.

    Deux bordereaux sont deposes en meme temps, l'un conforme et l'autre porteur d'un contrat inconnu.
    Le premier doit etre charge, le second rejete, et les lignes du premier doivent survivre.
    """
    lignes_avant = compte_lignes_brutes(session)
    depose_cotisations(espace_flux, lignes_conformes, code_emetteur="OCE")

    fautif = [dict(ligne) for ligne in lignes_conformes]
    fautif[0]["numero_contrat"] = "CT-2026-099999"
    depose_cotisations(espace_flux, fautif, code_emetteur="PYR", periode=date(2026, 6, 1))

    compte_rendu = lance_la_chaine(session)
    assert compte_rendu.traites == 1
    assert compte_rendu.rejetes == 1
    assert compte_lignes_brutes(session) == lignes_avant + 3, (
        "le lot conforme garde ses lignes, le lot rejete n'en ecrit aucune"
    )

def test_fichier_illisible_rejette_le_lot_sans_interrompre_la_chaine(session, espace_flux, lignes_conformes):
    """Un fichier qu'aucun lecteur ne sait ouvrir est rejete, et les lots suivants sont traites.

    Avant correction, l'exception du lecteur remontait jusqu'a l'appelant et interrompait la boucle :
    aucun lot suivant n'etait traite, et le defaut se reproduisait a chaque execution du graphe.
    """
    lignes_avant = compte_lignes_brutes(session)
    depose_cotisations(espace_flux, lignes_conformes, code_emetteur="OCE")

    # Un CSV encode en Latin-1, cas courant des exports francais, et un contenu qu'aucun decodeur
    # UTF-8 n'accepte.
    illisible = espace_flux / "arrivee" / "COTISATIONS_PYR_202606.csv"
    illisible.write_bytes("reference_appel;montant\nR1;caf\xe9 cr\xe8me\n".encode("latin-1"))

    compte_rendu = lance_la_chaine(session)
    assert compte_rendu.traites == 1, "le lot conforme doit etre charge malgre le fichier illisible"
    assert compte_rendu.rejetes == 1
    assert compte_lignes_brutes(session) == lignes_avant + 3

    lots = {lot.nom_fichier: lot for lot in session.scalars(select(LotFichier))}
    fautif = lots["COTISATIONS_PYR_202606.csv"]
    assert fautif.statut is StatutLot.REJETE
    assert CodeAnomalie.SCHEMA_INVALIDE.value in codes_bloquants(session, fautif)


def test_ligne_vide_en_fin_de_fichier_ne_masque_pas_le_total(session, espace_flux, lignes_conformes):
    """Un CSV termine par une ligne vide reste valide : le total est juste au-dessus.

    Les exports de tableur en produisent regulierement. Rejeter pour « ligne de total absente » un
    fichier qui en porte une serait un rejet a tort, et le plus agacant pour l'emetteur.
    """
    lignes_avant = compte_lignes_brutes(session)
    chemin = depose_cotisations(espace_flux, lignes_conformes)
    chemin.write_bytes(chemin.read_bytes() + b"\r\n\r\n")

    lance_la_chaine(session)
    lot = lot_unique(session)
    assert lot.statut is StatutLot.CHARGE, f"rejete a tort : {lot.motif_rejet}"
    assert compte_lignes_brutes(session) == lignes_avant + 3


def test_fichier_sans_ligne_de_donnee_est_rejete(session, espace_flux):
    """Un fichier reduit a son en-tete et a son total ne doit pas compter comme un mois servi.

    Un releve bancaire vide chargé marquerait la periode comme traitee, et tous les appels du mois
    seraient ensuite ecartes faute d'encaissement, sans que personne ne sache pourquoi.
    """
    lignes_avant = compte_lignes_brutes(session)
    depose_cotisations(espace_flux, [])
    lance_la_chaine(session)
    verifie_rejet_integral(session, CodeAnomalie.SCHEMA_INVALIDE, lignes_avant)


def test_periode_inversee_est_refusee(session, espace_flux, lignes_conformes):
    """Une periode dont la fin precede le debut viole une contrainte de la base.

    Sans ce controle, la violation se manifestait a l'ecriture, par une exception qui interrompait le
    traitement de tous les lots suivants. Une exception n'est pas un rejet.
    """
    lignes_avant = compte_lignes_brutes(session)
    ligne = lignes_conformes[0]
    ligne["periode_debut"], ligne["periode_fin"] = ligne["periode_fin"], ligne["periode_debut"]
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    verifie_rejet_integral(session, CodeAnomalie.SCHEMA_INVALIDE, lignes_avant)


def test_archive_ne_recouvre_pas_une_piece_deja_archivee(session, espace_flux, lignes_conformes):
    """Deux envois de meme nom et de contenu different laissent deux archives distinctes.

    C'est la promesse de la piste d'audit : un fichier archive n'est plus jamais modifie. Avant
    correction, le second envoi ecrasait le premier, dont l'empreinte enregistree ne correspondait
    alors plus a rien.
    """
    depose_cotisations(espace_flux, lignes_conformes)
    lance_la_chaine(session)
    premier = lot_unique(session)
    archives_apres_premier = sorted((espace_flux / "archive").rglob("*.csv"))
    assert len(archives_apres_premier) == 1

    # La compagnie renvoie un bordereau corrige, sous le meme nom.
    corrige = [dict(ligne) for ligne in lignes_conformes[:2]]
    depose_cotisations(espace_flux, corrige)
    lance_la_chaine(session)

    archives = sorted((espace_flux / "archive").rglob("*.csv"))
    assert len(archives) == 2, "le second envoi ne doit pas recouvrir le premier"
    lots = list(session.scalars(select(LotFichier)))
    assert len(lots) == 2
    for lot in lots:
        chemin = Path(lot.chemin_archive)
        assert chemin.exists(), f"archive manquante pour {lot.reference_lot}"
        assert empreinte_fichier(chemin) == lot.sha256, (
            "l'empreinte enregistree doit toujours decrire le fichier archive"
        )
    # Les deux lots ont des references distinctes. Sans `order by`, PostgreSQL rend les lignes dans l'ordre
    # physique, qui change apres une mise a jour : comparer a `lots[1]` passait ou echouait selon l'ordre.
    assert len({lot.reference_lot for lot in lots}) == 2
    assert premier.reference_lot in {lot.reference_lot for lot in lots}
