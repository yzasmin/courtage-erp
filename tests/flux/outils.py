"""Fonctions utilitaires des tests du module 2 : deposer un fichier, composer une ligne conforme.

Dans un module separe et non dans `conftest.py`, parce qu'un `conftest.py` n'est pas importable par son
nom : pytest le charge lui-meme, et `from tests.flux.conftest import ...` echoue des que `tests` n'est
pas un paquet. Les fixtures restent donc dans `conftest.py`, les fonctions appelables sont ici.
"""

from __future__ import annotations

from datetime import date

from courtage.flux import fichiers
from courtage.flux.enums import TypeFlux
from courtage.modeles.financier import AppelCotisation

#: Mois couvert par les fichiers des tests. Doit rester egal a celui de `conftest.PERIODE_TEST`.
PERIODE_TEST = date(2026, 6, 1)


def depose_cotisations(
    espace: object,
    lignes: list[dict],
    code_emetteur: str = "OCE",
    periode: date = PERIODE_TEST,
    totaux_forces: dict[str, int] | None = None,
    extension: str = "csv",
):
    """Ecrit un bordereau de cotisations dans le dossier d'arrivee et rend son chemin."""
    nom = f"COTISATIONS_{code_emetteur}_{periode:%Y%m}.{extension}"
    chemin = espace / "arrivee" / nom  # type: ignore[operator]
    if extension == "csv":
        fichiers.ecrit_csv(chemin, TypeFlux.COTISATIONS, lignes, totaux_forces)
    else:
        fichiers.ecrit_xlsx(chemin, TypeFlux.COTISATIONS, lignes, totaux_forces)
    return chemin


def depose_encaissements(espace, lignes: list[dict], periode: date = PERIODE_TEST):
    """Ecrit un releve bancaire dans le dossier d'arrivee et rend son chemin."""
    chemin = espace / "arrivee" / f"ENCAISSEMENTS_BANQUE_{periode:%Y%m}.csv"
    fichiers.ecrit_csv(chemin, TypeFlux.ENCAISSEMENTS, lignes)
    return chemin


def ligne_cotisation(appel: AppelCotisation, numero_contrat: str, numero_adherent: str, code_produit: str) -> dict:
    """Ligne de bordereau conforme, derivee d'un appel reellement enregistre."""
    return {
        "reference_appel": appel.reference_appel,
        "numero_contrat": numero_contrat,
        "numero_adherent": numero_adherent,
        "numero_police": None,
        "nombre_affilies": None,
        "code_produit": code_produit,
        "periode_debut": appel.periode_debut,
        "periode_fin": appel.periode_fin,
        "date_echeance": appel.date_echeance,
        "montant_ht": appel.montant_ht_cents,
        "montant_taxe": appel.montant_taxe_cents,
        "montant_total": appel.montant_total_cents,
    }


def ligne_encaissement(
    reference_bancaire: str,
    montant_cents: int,
    jour: date,
    reference_appel: str | None = None,
    numero_contrat: str | None = None,
) -> dict:
    return {
        "reference_bancaire": reference_bancaire,
        "date_operation": jour,
        "libelle": "VIREMENT TEST",
        "reference_appel": reference_appel,
        "numero_contrat": numero_contrat,
        "numero_police": None,
        "moyen": "virement",
        "montant": montant_cents,
    }
