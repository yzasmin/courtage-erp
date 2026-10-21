"""Prouve que les migrations montent et redescendent proprement, sur le moteur configure.

Critere d'acceptation du module 1 : « migrations qui montent et descendent proprement ». Ce que le
script etablit, dans l'ordre :

1. le schema part de zero, puis monte revision par revision ;
2. a la derniere revision, les 23 tables attendues existent ;
3. le schema redescend revision par revision jusqu'a zero, sans erreur ;
4. apres la descente, il ne reste que la table de version d'Alembic, donc rien n'a ete oublie ;
5. le schema remonte, pour verifier que la descente n'a pas laisse d'etat qui empecherait un nouveau
   deploiement.

Le point 4 est celui qui attrape les vraies erreurs : une migration qui cree un index ou une contrainte
sans la supprimer dans sa descente laisse un residu, et la base devient impossible a remonter
proprement. Sur SQLite, la descente n'est possible que grace au mode « batch » configure dans
`migrations/env.py`.

Usage : `python -m uv run python scripts/preuve_migrations.py`
"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from courtage.config import RACINE_PROJET
from courtage.db import cree_moteur
from courtage.modeles import Base

# Les tables de la chaine des flux financiers vivent dans leur propre paquet. Les importer remplit
# `Base.metadata`, sans quoi ce script les verrait comme des tables « en trop » au sommet des
# migrations. L'import est tolerant : le module 1 doit rester verifiable seul.
try:  # pragma: no cover - depend de l'avancement du module 2
    import courtage.flux.modeles  # noqa: F401
except ImportError:  # pragma: no cover
    pass

#: Table interne d'Alembic : elle survit a la descente, c'est normal et voulu.
TABLE_DE_VERSION = "alembic_version"


def _config() -> Config:
    config = Config(str(RACINE_PROJET / "alembic.ini"))
    config.set_main_option("script_location", str(RACINE_PROJET / "migrations"))
    return config


def _tables_presentes() -> set[str]:
    """Liste les tables, puis **ferme tout** avant de rendre la main.

    Le detail qui coute une demi-heure a qui ne le connait pas. Garder un moteur d'inspection ouvert
    pendant que les migrations tournent bloque le `DROP TABLE` suivant sur PostgreSQL : la connexion
    laissee dans la reserve du moteur detient encore un verrou de lecture sur la table, et la commande
    de suppression attend indefiniment, sans message d'erreur. SQLite ne s'en apercoit pas, le script
    passait donc en local et se figeait sur la base du compose.

    Chaque appel cree donc son moteur, lit, et le libere. Le cout est de quelques centiemes de seconde,
    et le script ne peut plus se bloquer lui-meme.
    """
    moteur = cree_moteur(echo=False)
    try:
        return set(inspect(moteur).get_table_names())
    finally:
        moteur.dispose()


def _vide_le_schema() -> None:
    """Supprime toutes les tables reellement presentes, y compris la table de version d'Alembic."""
    from sqlalchemy import MetaData

    moteur = cree_moteur(echo=False)
    try:
        schema = MetaData()
        schema.reflect(bind=moteur)
        if not schema.tables:
            return
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


def _nom_du_moteur() -> str:
    moteur = cree_moteur(echo=False)
    try:
        return moteur.dialect.name
    finally:
        moteur.dispose()


def main() -> int:
    config = _config()
    nom_moteur = _nom_du_moteur()

    revisions = [r.revision for r in reversed(list(ScriptDirectory.from_config(config).walk_revisions()))]
    tables_attendues = set(Base.metadata.tables)

    etapes: list[dict] = []
    debut_total = time.monotonic()

    print(f"moteur : {nom_moteur}")
    print(f"revisions declarees : {', '.join(revisions)}")

    # 1. Repartir d'un schema reellement vide.
    #
    # Une descente complete ne suffit pas quand la base contient deja le jeu de demonstration : la
    # revision 0003 rend l'appel de cotisation capable de s'adresser a une police collective, et le
    # schema precedent ne sait pas representer un appel sans contrat. Sa descente est donc possible
    # sur un schema vide, et impossible une fois des appels groupes enregistres. C'est une propriete
    # de la migration, documentee dans `docs/modele-donnees.md`, et ce script la contourne en
    # supprimant les tables plutot qu'en redescendant des donnees.
    _vide_le_schema()

    # 2. Montee revision par revision.
    for revision in revisions:
        debut = time.monotonic()
        command.upgrade(config, revision)
        duree = time.monotonic() - debut
        tables = _tables_presentes()
        etapes.append(
            {
                "sens": "montee",
                "revision": revision,
                "duree_s": round(duree, 3),
                "tables_apres": len(tables - {TABLE_DE_VERSION}),
            }
        )
        print(f"  montee   -> {revision} : {len(tables - {TABLE_DE_VERSION})} tables, {duree:.2f} s")

    tables_au_sommet = _tables_presentes() - {TABLE_DE_VERSION}
    manquantes = sorted(tables_attendues - tables_au_sommet)
    en_trop = sorted(tables_au_sommet - tables_attendues)

    # 3. Descente revision par revision.
    for revision in reversed(revisions):
        cible = revisions[revisions.index(revision) - 1] if revisions.index(revision) > 0 else "base"
        debut = time.monotonic()
        command.downgrade(config, cible)
        duree = time.monotonic() - debut
        tables = _tables_presentes()
        etapes.append(
            {
                "sens": "descente",
                "revision": revision,
                "vers": cible,
                "duree_s": round(duree, 3),
                "tables_apres": len(tables - {TABLE_DE_VERSION}),
            }
        )
        print(f"  descente <- {revision} vers {cible} : {len(tables - {TABLE_DE_VERSION})} tables, {duree:.2f} s")

    residus = sorted(_tables_presentes() - {TABLE_DE_VERSION})

    # 4. Remontee, pour verifier que la descente laisse une base redeployable.
    debut = time.monotonic()
    command.upgrade(config, "head")
    duree_remontee = time.monotonic() - debut
    tables_apres_remontee = _tables_presentes() - {TABLE_DE_VERSION}
    print(f"  remontee -> head : {len(tables_apres_remontee)} tables, {duree_remontee:.2f} s")

    conforme = not manquantes and not en_trop and not residus and tables_apres_remontee == tables_attendues

    rapport = {
        "mesure_le": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moteur": nom_moteur,
        "python": platform.python_version(),
        "revisions": revisions,
        "conforme": conforme,
        "tables_attendues": len(tables_attendues),
        "tables_au_sommet": len(tables_au_sommet),
        "tables_manquantes_au_sommet": manquantes,
        "tables_en_trop_au_sommet": en_trop,
        "residus_apres_descente_complete": residus,
        "tables_apres_remontee": len(tables_apres_remontee),
        "duree_totale_s": round(time.monotonic() - debut_total, 2),
        "etapes": etapes,
    }

    dossier = RACINE_PROJET / "results"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"migrations_{nom_moteur}.json"
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    if conforme:
        print(
            f"CONFORME : {len(revisions)} revisions montees et redescendues sur {nom_moteur},"
            f" {len(tables_attendues)} tables, aucun residu apres la descente complete"
        )
    else:
        print("NON CONFORME", file=sys.stderr)
        if manquantes:
            print(f"  tables manquantes au sommet : {manquantes}", file=sys.stderr)
        if en_trop:
            print(f"  tables en trop au sommet : {en_trop}", file=sys.stderr)
        if residus:
            print(f"  residus apres la descente : {residus}", file=sys.stderr)
    print(f"rapport : {chemin}")

    return 0 if conforme else 1


if __name__ == "__main__":
    raise SystemExit(main())
