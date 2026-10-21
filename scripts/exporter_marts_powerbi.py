"""Exporte les marts du modele en etoile vers `powerbi/donnees/*.csv`, la source du projet Power BI.

Pourquoi des CSV et non une connexion directe a PostgreSQL : le projet doit s'ouvrir sur un poste sans
pilote PostgreSQL et sans identifiants, et la lecture d'un fichier local ne demande aucun secret. Les
colonnes exportees sont celles que le modele semantique declare : ni nom, ni prenom, ni coordonnees.

Usage :
    COURTAGE_BASE_URL=postgresql+psycopg://... python -m uv run python scripts/exporter_marts_powerbi.py
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text

RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "powerbi" / "donnees"

# table du mart -> colonnes exportees, dans l'ordre attendu par le modele semantique
TABLES: dict[str, list[str]] = {
    "dim_date": [
        "date_jour", "annee", "trimestre", "mois", "annee_mois", "annee_trimestre", "est_dernier_jour_du_mois",
    ],
    "dim_produit": ["produit_id", "code_produit", "libelle_produit", "gestion_prestations_deleguee"],
    "dim_branche": ["branche_id", "code_branche", "libelle_branche"],
    "dim_compagnie": ["compagnie_id", "code_compagnie", "raison_sociale"],
    "dim_apporteur": ["apporteur_id", "code_apporteur", "nom_apporteur", "type_apporteur"],
    "dim_adherent": ["adherent_id", "numero_adherent", "sexe", "departement", "type_couverture", "tranche_age"],
    "fct_cotisations": [
        "appel_id", "date_echeance", "produit_id", "compagnie_id", "branche_id", "apporteur_id", "cotisation_ht_euros",
    ],
    "fct_cotisations_acquises": [
        "appel_id", "mois_acquisition", "produit_id", "compagnie_id", "branche_id", "apporteur_id",
        "cotisation_acquise_ht_euros",
    ],
    "fct_prestations": [
        "prestation_id", "date_soins", "date_reglement", "statut_prestation", "produit_id", "compagnie_id",
        "branche_id", "apporteur_id", "adherent_id", "demande_euros", "rembourse_euros",
    ],
    "fct_mouvements_portefeuille": [
        "mouvement_id", "type_mouvement", "date_mouvement", "date_effet_contrat", "motif_resiliation",
        "tranche_age_au_mouvement", "anciennete_en_mois", "produit_id", "compagnie_id", "branche_id",
        "apporteur_id", "adherent_id", "cotisation_annualisee_euros",
    ],
    "fct_portefeuille_mensuel": [
        "date_cliche", "contrat_id", "statut_contrat", "produit_id", "compagnie_id", "branche_id",
        "apporteur_id", "adherent_id", "cotisation_mensuelle_euros", "cotisation_annualisee_euros",
    ],
}


def valeur(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, date):
        return v.isoformat()
    return v


def main() -> int:
    url = os.environ.get("COURTAGE_BASE_URL", "")
    if not url.startswith("postgresql"):
        print("Les marts dbt n'existent que sur PostgreSQL : renseigner COURTAGE_BASE_URL.", file=sys.stderr)
        return 2
    DOSSIER.mkdir(parents=True, exist_ok=True)
    moteur = create_engine(url)
    with moteur.connect() as connexion:
        for table, colonnes in TABLES.items():
            requete = f"select {', '.join(colonnes)} from analytique_marts.{table} order by 1"
            lignes = connexion.execute(text(requete)).all()
            if not lignes:
                print(f"{table} : vide, export refuse", file=sys.stderr)
                return 1
            with (DOSSIER / f"{table}.csv").open("w", encoding="utf-8", newline="") as sortie:
                ecrivain = csv.writer(sortie)
                ecrivain.writerow(colonnes)
                ecrivain.writerows([valeur(v) for v in ligne] for ligne in lignes)
            print(f"{table} : {len(lignes)} lignes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
