"""Execute les requetes de controle des indicateurs (sql/kpi/*.sql) sur les marts PostgreSQL.

Les marts dbt n'existent que sur PostgreSQL : la commande refuse de tourner sur SQLite plutot que de
produire un resultat vide. Sortie : `results/kpi_sql.json`, relue par `docs/kpi.md` et par le script de
concordance avec Power BI. Aucune valeur n'est ecrite a la main.

Usage : COURTAGE_BASE_URL=postgresql+psycopg://... python -m uv run python scripts/preuve_kpi.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text

RACINE = Path(__file__).resolve().parents[1]
REQUETES = RACINE / "sql" / "kpi"
SORTIE = RACINE / "results" / "kpi_sql.json"


def convertit(valeur):
    if isinstance(valeur, Decimal):
        return float(valeur)
    if isinstance(valeur, date):
        return valeur.isoformat()
    return valeur


def main() -> int:
    url = os.environ.get("COURTAGE_BASE_URL", "")
    if not url.startswith("postgresql"):
        print("Les marts dbt n'existent que sur PostgreSQL : renseigner COURTAGE_BASE_URL.", file=sys.stderr)
        return 2
    moteur = create_engine(url)
    resultats: dict[str, list[dict]] = {}
    with moteur.connect() as connexion:
        for fichier in sorted(REQUETES.glob("*.sql")):
            lignes = connexion.execute(text(fichier.read_text(encoding="utf-8"))).mappings().all()
            if not lignes:
                print(f"{fichier.name} : aucun resultat, la preuve ne prouve rien", file=sys.stderr)
                return 1
            resultats[fichier.stem] = [{k: convertit(v) for k, v in ligne.items()} for ligne in lignes]
            print(f"{fichier.name} : {len(lignes)} lignes")
    SORTIE.write_text(json.dumps(resultats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"compte rendu : {SORTIE.relative_to(RACINE).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
