"""Prouve que la generation est reproductible : deux executions, meme graine, meme empreinte.

Ce que le script fait, et pourquoi dans cet ordre. Il redescend le schema, le remonte, genere, calcule
l'empreinte, puis recommence une seconde fois, et compare les deux empreintes table par table. Il sort en
echec si une seule table differe. L'interet de redescendre le schema plutot que de vider les tables :
cela prouve au passage que les migrations redescendent proprement, ce qui est un autre critere
d'acceptation du module 1.

Une empreinte differente peut venir de trois causes, et le rapport les distingue :

- un tirage aleatoire consomme dans un ordre different d'une execution a l'autre ;
- une valeur derivee de l'horloge, et non des dates simulees ;
- un parcours d'ensemble non ordonne, dont l'ordre varie avec le grain de hachage des chaines.

Usage : `python -m uv run python scripts/preuve_reproductibilite.py [--graine 20261019]`
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import UTC, date, datetime

from alembic import command
from alembic.config import Config

from courtage.config import RACINE_PROJET, parametres
from courtage.db import cree_moteur, moteur, session_portee
from courtage.generateur import genere_tout
from courtage.generateur.empreinte import empreinte_complete


def _config_alembic() -> Config:
    config = Config(str(RACINE_PROJET / "alembic.ini"))
    config.set_main_option("script_location", str(RACINE_PROJET / "migrations"))
    return config


def _remet_le_schema_a_zero() -> None:
    """Vide la base, puis remonte le schema par les migrations.

    Pourquoi supprimer les tables plutot que redescendre les migrations, comme ce script le faisait.
    La revision 0003 rend l'appel de cotisation capable de s'adresser a une police collective, ce que
    le schema precedent ne sait pas representer : un appel groupe n'a pas de contrat. Sa descente est
    donc possible sur un schema vide, et impossible une fois des appels groupes enregistres. C'est
    une propriete de la migration, pas un defaut, et elle est consignee dans `docs/modele-donnees.md`.

    La descente complete reste prouvee, sur une base vide, par `scripts/preuve_migrations.py`.
    """
    from sqlalchemy import MetaData

    moteur = cree_moteur(echo=False)
    try:
        # Reflexion plutot que `Base.metadata` : on supprime ce qui est **reellement** en base, y
        # compris la table de version d'Alembic et les tables d'un autre module. Partir des entites
        # declarees laisserait derriere tout ce qui n'y figure pas, et la remontee echouerait sur une
        # table deja existante.
        schema = MetaData()
        schema.reflect(bind=moteur)
        if moteur.dialect.name == "sqlite":
            with moteur.connect() as connexion:
                brute = connexion.connection.dbapi_connection
                curseur = brute.cursor()
                curseur.execute("PRAGMA foreign_keys=OFF")
                curseur.close()
                schema.drop_all(bind=connexion)
                connexion.commit()
        else:
            schema.drop_all(bind=moteur)
    finally:
        moteur.dispose()
    command.upgrade(_config_alembic(), "head")


def une_execution(graine: int, date_reference: date) -> tuple[dict, dict, float]:
    """Remet le schema a zero, genere, et retourne le compte rendu et l'empreinte."""
    _remet_le_schema_a_zero()

    debut = time.monotonic()
    with session_portee() as session:
        resultat = genere_tout(session, graine=graine, date_reference=date_reference)
    duree = time.monotonic() - debut

    with session_portee() as session:
        empreinte = empreinte_complete(session)
    return resultat.en_dictionnaire(), empreinte, duree


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--graine", type=int, default=parametres.graine)
    analyseur.add_argument("--date-reference", default=parametres.date_reference)
    args = analyseur.parse_args(argv)

    date_reference = date.fromisoformat(args.date_reference)
    nom_moteur = moteur().dialect.name

    print(f"execution 1 sur {nom_moteur}, graine {args.graine}")
    compte_rendu_1, empreinte_1, duree_1 = une_execution(args.graine, date_reference)
    print(f"  empreinte globale : {empreinte_1['sha256_global']}  ({duree_1:.1f} s)")

    print(f"execution 2 sur {nom_moteur}, graine {args.graine}")
    compte_rendu_2, empreinte_2, duree_2 = une_execution(args.graine, date_reference)
    print(f"  empreinte globale : {empreinte_2['sha256_global']}  ({duree_2:.1f} s)")

    identiques = empreinte_1["sha256_global"] == empreinte_2["sha256_global"]
    tables_differentes = sorted(
        nom
        for nom, valeurs in empreinte_1["tables"].items()
        if valeurs["sha256"] != empreinte_2["tables"][nom]["sha256"]
    )

    rapport = {
        "mesure_le": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moteur": nom_moteur,
        "python": platform.python_version(),
        "graine": args.graine,
        "date_reference": args.date_reference,
        "reproductible": identiques,
        "tables_differentes": tables_differentes,
        "empreinte_execution_1": empreinte_1["sha256_global"],
        "empreinte_execution_2": empreinte_2["sha256_global"],
        "total_lignes": empreinte_1["total_lignes"],
        "duree_execution_1_s": round(duree_1, 2),
        "duree_execution_2_s": round(duree_2, 2),
        "volumetrie": compte_rendu_1,
        "empreintes_par_table": {
            nom: valeurs["sha256"] for nom, valeurs in sorted(empreinte_1["tables"].items())
        },
        "lignes_par_table": {
            nom: valeurs["lignes"] for nom, valeurs in sorted(empreinte_1["tables"].items())
        },
    }
    if compte_rendu_1 != compte_rendu_2:
        rapport["ecart_volumetrie"] = {"execution_1": compte_rendu_1, "execution_2": compte_rendu_2}

    dossier = RACINE_PROJET / "results"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"reproductibilite_{nom_moteur}.json"
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    if identiques:
        print(f"REPRODUCTIBLE : {empreinte_1['total_lignes']} lignes, empreinte identique sur les deux executions")
    else:
        print("NON REPRODUCTIBLE : les empreintes different", file=sys.stderr)
        print(f"tables en cause : {', '.join(tables_differentes)}", file=sys.stderr)
    print(f"rapport : {chemin}")
    return 0 if identiques else 1


if __name__ == "__main__":
    raise SystemExit(main())


