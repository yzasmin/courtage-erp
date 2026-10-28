"""Assemble le depot de la demonstration en ligne, heberge sur Render.

Ce depot est a part. Ce script y copie le code de l'application, le Dockerfile et le README de la
demonstration, puis construit `demo.db` : la base SQLite locale (`courtage.db`, generee par `courtage generer`
puis `courtage ia traiter`), a laquelle il ajoute les scores de resiliation exportes de PostgreSQL dans
`data/demo/scores_resiliation.csv`, rattaches par numero de contrat. Les scores ne se calculent que sur
PostgreSQL, parce que leurs variables viennent d'un modele dbt.

Usage : python deploy/demo/preparer.py ../courtage-erp-demo
"""

from __future__ import annotations

import csv
import shutil
import sqlite3
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
ICI = Path(__file__).resolve().parent
A_COPIER = ["pyproject.toml", "uv.lock", "README.md", "alembic.ini", "migrations", "src"]


def construit_base(cible: Path) -> int:
    shutil.copyfile(RACINE / "courtage.db", cible)
    base = sqlite3.connect(cible)
    ids = dict(base.execute("select numero_contrat, id from contrat"))
    with open(RACINE / "data" / "demo" / "scores_resiliation.csv", encoding="utf-8") as fichier:
        lignes = [
            (ids[s["numero_contrat"]], s["date_observation"], float(s["probabilite"]), int(s["decile"]),
             s["facteur_1"] or None, s["facteur_2"] or None, s["facteur_3"] or None, s["version_modele"],
             s["calcule_le"])
            for s in csv.DictReader(fichier)
        ]
    base.execute("delete from score_resiliation")
    base.executemany(
        "insert into score_resiliation (contrat_id, date_observation, probabilite, decile, facteur_1,"
        " facteur_2, facteur_3, version_modele, calcule_le) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lignes,
    )
    base.commit()
    base.execute("vacuum")
    base.close()
    return len(lignes)


def main() -> None:
    sortie = Path(sys.argv[1]).resolve()
    sortie.mkdir(parents=True, exist_ok=True)
    erp = sortie / "erp"
    if erp.exists():
        shutil.rmtree(erp)
    for nom in A_COPIER:
        source = RACINE / nom
        if source.is_dir():
            shutil.copytree(source, erp / nom, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            erp.mkdir(exist_ok=True)
            shutil.copyfile(source, erp / nom)
    shutil.copyfile(ICI / "Dockerfile", sortie / "Dockerfile")
    shutil.copyfile(ICI / "README.md", sortie / "README.md")
    print(f"{construit_base(sortie / 'demo.db')} scores ajoutes a {sortie / 'demo.db'}")


if __name__ == "__main__":
    main()
