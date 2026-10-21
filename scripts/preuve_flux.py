"""Preuves executables du module 2 : rejet integral d'un lot, et idempotence de la chaine.

Deux affirmations de la specification ne se demontrent pas par une relecture de code. Ce script les
mesure, sur la base reellement configuree, et ecrit ses constats dans `results/`.

**Rejet integral.** Un echec de controle bloquant rejette le lot entier, sans aucune ecriture partielle.
La preuve compte les lignes de la couche brute avant et apres le chargement, lot par lot, et verifie
qu'aucun lot rejete n'a laisse de ligne derriere lui. Le compte porte sur les lignes **reellement
presentes** en base, et non sur le compteur du journal : un compteur peut mentir, une requete de
comptage non.

**Idempotence.** Rejouer le meme fichier ne change rien. La preuve redepose dans le dossier d'arrivee
tous les fichiers deja archives, sous leur nom d'origine, puis rejoue la chaine entiere et compare deux
empreintes SHA-256 : celle de l'etat de la base avant, celle de l'etat apres. Redeposer les fichiers est
plus exigeant que relancer la chaine a vide, puisque c'est exactement le geste d'un emetteur qui renvoie
son courrier.

Le script ne genere pas les fichiers : il travaille sur l'espace de flux existant, pour pouvoir etre
lance apres une execution du graphe Airflow aussi bien qu'apres `courtage flux chaine`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from sqlalchemy import func, select

from courtage.db import moteur, session_portee
from courtage.flux import bordereaux as module_bordereaux
from courtage.flux import commissions as module_commissions
from courtage.flux import ingestion
from courtage.flux.cli import dossier_resultats
from courtage.flux.enums import StatutLot
from courtage.flux.modeles import (
    AnomalieLot,
    BrutCotisation,
    BrutEncaissement,
    BrutPrestation,
    LotFichier,
    RapprochementLigne,
)
from courtage.flux.rapprochement import rapproche
from courtage.modeles.financier import Bordereau, Commission, Retrocession

#: Tables dont l'etat est pris en compte dans l'empreinte d'idempotence. Ce sont celles que la chaine
#: ecrit : si l'une d'elles bouge au second passage, la chaine n'est pas idempotente.
TABLES_SUIVIES = (
    LotFichier,
    AnomalieLot,
    BrutCotisation,
    BrutEncaissement,
    BrutPrestation,
    RapprochementLigne,
    Commission,
    Retrocession,
    Bordereau,
)


def _ecrit(nom: str, contenu: dict) -> Path:
    dossier = dossier_resultats()
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chemin


def _comptes(session) -> dict[str, int]:
    """Nombre de lignes de chaque table ecrite par la chaine."""
    return {
        entite.__tablename__: session.scalar(select(func.count()).select_from(entite)) or 0
        for entite in TABLES_SUIVIES
    }


def _empreinte_etat(session) -> str:
    """Empreinte SHA-256 de l'etat des tables ecrites par la chaine.

    Les colonnes d'horodatage sont volontairement exclues : `detecte_le`, `traite_le` et `calcule_le`
    changent a chaque execution sans que rien de metier ne change, et les inclure rendrait toute chaine
    non idempotente par construction. Ce qui est empreinte, ce sont les faits : quel lot, quel verdict,
    quelles lignes, quels montants.
    """
    condensat = hashlib.sha256()
    horodatages = {"detecte_le", "traite_le", "calcule_le", "cree_le", "maj_le"}
    for entite in TABLES_SUIVIES:
        table = entite.__table__
        colonnes = [colonne for colonne in table.columns if colonne.name not in horodatages]
        requete = select(*colonnes).order_by(*[table.c[nom] for nom in ("id",) if nom in table.c])
        condensat.update(table.name.encode("utf-8"))
        for ligne in session.execute(requete):
            condensat.update("|".join("" if valeur is None else str(valeur) for valeur in ligne).encode("utf-8"))
            condensat.update(b"\n")
    return condensat.hexdigest()


def _lots_par_statut(session) -> dict[str, int]:
    requete = select(LotFichier.statut, func.count(LotFichier.id)).group_by(LotFichier.statut)
    return {statut.value: nombre for statut, nombre in session.execute(requete)}


def _lignes_brutes_par_lot(session) -> dict[int, int]:
    """Lignes reellement presentes en couche brute, lot par lot."""
    comptes: dict[int, int] = {}
    for entite in (BrutCotisation, BrutEncaissement, BrutPrestation):
        requete = select(entite.lot_id, func.count(entite.id)).group_by(entite.lot_id)
        for lot_id, nombre in session.execute(requete):
            comptes[lot_id] = comptes.get(lot_id, 0) + nombre
    return comptes


def preuve_rejet_integral() -> int:
    """Verifie qu'aucun lot rejete n'a laisse de ligne en couche brute, et l'ecrit dans `results/`."""
    with session_portee() as session:
        lignes_par_lot = _lignes_brutes_par_lot(session)
        lots = list(session.scalars(select(LotFichier).order_by(LotFichier.nom_fichier)))

        rejetes: list[dict[str, object]] = []
        fautifs: list[str] = []
        for lot in lots:
            if lot.statut is not StatutLot.REJETE:
                continue
            presentes = lignes_par_lot.get(lot.id, 0)
            codes = sorted(
                {
                    code.value
                    for code in session.scalars(
                        select(AnomalieLot.code).where(
                            AnomalieLot.lot_id == lot.id, AnomalieLot.severite == "bloquant"
                        )
                    )
                }
            )
            rejetes.append(
                {
                    "reference_lot": lot.reference_lot,
                    "nom_fichier": lot.nom_fichier,
                    "type_flux": lot.type_flux.value,
                    "lignes_dans_le_fichier": lot.nombre_lignes_fichier,
                    "lignes_annoncees_chargees": lot.nombre_lignes_chargees,
                    "lignes_reellement_en_base": presentes,
                    "codes_bloquants": codes,
                    "motif": lot.motif_rejet,
                }
            )
            if presentes != 0 or lot.nombre_lignes_chargees != 0:
                fautifs.append(lot.reference_lot)

        charges = [lot for lot in lots if lot.statut is StatutLot.CHARGE]
        incoherents = [
            lot.reference_lot
            for lot in charges
            if lot.nombre_lignes_chargees != lignes_par_lot.get(lot.id, 0)
        ]

        contenu = {
            "moteur": moteur().dialect.name,
            "lots_par_statut": _lots_par_statut(session),
            "lots_rejetes": len(rejetes),
            "lignes_rejetees_au_total": sum(int(ligne["lignes_dans_le_fichier"]) for ligne in rejetes),
            "lots_rejetes_ayant_ecrit": fautifs,
            "lots_charges": len(charges),
            "lots_charges_au_compteur_incoherent": incoherents,
            # Meme garde-fou : sur une base vierge, aucun lot rejete ne donnerait « conforme » sans que
        # rien n'ait ete verifie. La preuve exige donc au moins un lot rejete et un lot charge.
        "conforme": bool(rejetes) and bool(charges) and not fautifs and not incoherents,
            "detail": rejetes,
        }

    chemin = _ecrit("flux_rejet_integral.json", contenu)
    print("preuve du rejet integral")
    print(f"  lots rejetes                         {contenu['lots_rejetes']}")
    print(f"  lignes contenues dans ces lots       {contenu['lignes_rejetees_au_total']}")
    print(f"  lots rejetes ayant ecrit une ligne   {len(fautifs)}")
    print(f"  lots charges au compteur incoherent  {len(incoherents)}")
    print(f"  verdict                              {'conforme' if contenu['conforme'] else 'NON CONFORME'}")
    print(f"compte rendu : {chemin}")
    return 0 if contenu["conforme"] else 1


def _redepose_les_archives(session) -> list[str]:
    """Recopie dans le dossier d'arrivee chaque fichier archive, **sous son nom d'origine**.

    Le nom d'origine, et non celui du fichier archive. Depuis que l'archive suffixe ses fichiers par
    leur empreinte, pour qu'un renvoi corrige ne recouvre jamais la piece d'audit precedente, recopier
    le nom de l'archive reviendrait a deposer un fichier que la chaine n'a jamais vu : elle creerait un
    lot de plus, et la preuve mesurerait l'inverse de ce qu'elle annonce. Le nom d'origine est dans le
    journal, colonne `nom_fichier`.
    """
    arrivee = ingestion.dossier_arrivee()
    arrivee.mkdir(parents=True, exist_ok=True)
    redeposes: list[str] = []
    requete = select(LotFichier.nom_fichier, LotFichier.chemin_archive).where(
        LotFichier.chemin_archive.is_not(None)
    )
    for nom_fichier, chemin_archive in session.execute(requete):
        source = Path(chemin_archive)
        if source.exists():
            shutil.copyfile(source, arrivee / nom_fichier)
            redeposes.append(nom_fichier)
    return sorted(redeposes)


def _rejoue_la_chaine() -> dict[str, object]:
    """Rejoue les sept etapes de la chaine, hors dbt, et rend leurs comptes rendus."""
    with session_portee() as session:
        detection = ingestion.detecte(session)
        archivage = ingestion.archive(session)
        chargement = ingestion.charge(session)
        rapprochement = rapproche(session)
        calcul = module_commissions.calcule(session)
        edition = module_bordereaux.produit(session)
    return {
        "detection": detection.en_dictionnaire(),
        "archivage": archivage.en_dictionnaire(),
        "chargement": chargement.en_dictionnaire(),
        "rapprochement": rapprochement.en_dictionnaire(),
        "commissions": calcul.en_dictionnaire(),
        "bordereaux": edition.en_dictionnaire(),
    }


def _sans_details(comptes_rendus: dict[str, object]) -> dict[str, object]:
    """Retire les listes de details, qui citent des chemins et ne servent pas a la comparaison."""
    volumineuses = ("details", "fichiers", "lots", "bordereaux_en_base")
    allege: dict[str, object] = {}
    for etape, contenu in comptes_rendus.items():
        if isinstance(contenu, dict):
            allege[etape] = {
                cle: valeur for cle, valeur in contenu.items() if cle not in volumineuses
            }
        else:
            allege[etape] = contenu
    return allege


def preuve_idempotence() -> int:
    """Redepose les fichiers deja traites, rejoue la chaine, et compare l'etat avant et apres."""
    with session_portee() as session:
        comptes_avant = _comptes(session)
        empreinte_avant = _empreinte_etat(session)

    with session_portee() as session:
        redeposes = _redepose_les_archives(session)
    comptes_rendus = _rejoue_la_chaine()

    with session_portee() as session:
        comptes_apres = _comptes(session)
        empreinte_apres = _empreinte_etat(session)
        moteur_nom = moteur().dialect.name

    ecarts = {
        table: {"avant": comptes_avant[table], "apres": comptes_apres[table]}
        for table in comptes_avant
        if comptes_avant[table] != comptes_apres[table]
    }
    contenu = {
        "moteur": moteur_nom,
        "fichiers_redeposes": len(redeposes),
        "noms_redeposes": redeposes,
        "comptes_avant": comptes_avant,
        "comptes_apres": comptes_apres,
        "tables_modifiees": ecarts,
        "empreinte_avant": empreinte_avant,
        "empreinte_apres": empreinte_apres,
        "empreintes_identiques": empreinte_avant == empreinte_apres,
        # Une preuve qui conclurait sur un perimetre vide ne prouverait rien : sans archive, aucun
        # fichier n'est redepose, les empreintes sont forcement identiques et le verdict serait
        # « conforme » sans que la chaine ait rejoue quoi que ce soit.
        "conforme": bool(redeposes) and empreinte_avant == empreinte_apres and not ecarts,
        "comptes_rendus_du_second_passage": _sans_details(comptes_rendus),
    }

    chemin = _ecrit("flux_idempotence.json", contenu)
    print("preuve d'idempotence")
    print(f"  fichiers redeposes                   {len(redeposes)}")
    print(f"  empreinte avant                      {empreinte_avant}")
    print(f"  empreinte apres                      {empreinte_apres}")
    print(f"  tables modifiees                     {len(ecarts)}")
    print(f"  verdict                              {'conforme' if contenu['conforme'] else 'NON CONFORME'}")
    print(f"compte rendu : {chemin}")
    return 0 if contenu["conforme"] else 1


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="preuve_flux",
        description="Preuves du module 2 : rejet integral d'un lot, et idempotence de la chaine.",
    )
    analyseur.add_argument(
        "--preuve",
        choices=["rejet", "idempotence", "toutes"],
        default="toutes",
        help="preuve a produire",
    )
    args = analyseur.parse_args(argv)

    code = 0
    if args.preuve in ("rejet", "toutes"):
        code |= preuve_rejet_integral()
    if args.preuve in ("idempotence", "toutes"):
        code |= preuve_idempotence()
    return code


if __name__ == "__main__":
    sys.exit(main())
