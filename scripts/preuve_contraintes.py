"""Prouve que la base refuse elle-même les écritures incohérentes, par insertion SQL directe.

Pourquoi ce script existe en plus des tests. Les tests de `tests/test_integrite.py` passent par
SQLAlchemy, qui ajoute sa propre validation. Et le contrôle de non-dérive du schéma repose sur
`alembic.autogenerate.compare_metadata`, qui **ne compare pas les contraintes de vérification** : trois
règles déclarées dans le modèle ont ainsi vécu plusieurs révisions sans jamais être émises en base, sans
qu'aucun test ne tombe. Ce script ferme ce trou en écrivant du SQL directement sur la connexion, et en
exigeant un refus du moteur.

Ce qu'il établit, pour chaque règle : une insertion qui la viole est refusée, et le message du moteur
nomme la contrainte. Il tourne sur le moteur désigné par `COURTAGE_BASE_URL`, donc sur SQLite comme sur
PostgreSQL, et l'intégration continue l'exécute sur les deux.

Il n'écrit rien de durable : chaque tentative vit dans sa propre transaction, annulée quel qu'en soit le
résultat.

Usage : `python -m uv run python scripts/preuve_contraintes.py`
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from courtage.config import RACINE_PROJET
from courtage.db import cree_moteur

#: Gabarit d'insertion d'un appel de cotisation. Les montants sont cohérents entre eux, pour que le
#: refus attendu vienne de la règle visée et non d'une autre contrainte.
INSERTION_APPEL = (
    "INSERT INTO appel_cotisation (reference_appel, contrat_id, police_id, nombre_affilies,"
    " periode_debut, periode_fin, date_echeance, montant_ht_cents, montant_taxe_cents,"
    " montant_total_cents, taux_taxe_bp, statut)"
    " VALUES ('{reference}', {contrat}, {police}, {affilies}, '2099-01-01', '2099-01-31',"
    " '2099-01-05', 10000, 1375, 11375, 1375, 'attendu')"
)

#: Gabarit d'insertion d'une commission. Le taux et le montant respectent les autres contraintes de la
#: table, pour la même raison.
INSERTION_COMMISSION = (
    "INSERT INTO commission (appel_id, contrat_id, police_id, compagnie_id, produit_id, periode,"
    " assiette_cents, taux_bp, montant_cents)"
    " VALUES ({appel}, {contrat}, {police}, {compagnie}, {produit}, '2099-01-01', 10000, 1000, 1000)"
)


@dataclass(frozen=True, slots=True)
class Tentative:
    """Une écriture qui doit être refusée, et la contrainte censée la refuser."""

    regle: str
    contrainte: str
    sql: str
    pourquoi: str


def _cles(connexion) -> dict[str, int]:
    """Lit en base un contrat, une police, un appel et son référentiel.

    Les clés sont lues et non inventées : une clé inexistante serait refusée par la clé étrangère, et la
    preuve ne dirait alors rien de la contrainte visée.
    """
    cles = {
        "contrat": connexion.execute(
            text("SELECT id FROM contrat WHERE police_id IS NULL ORDER BY id LIMIT 1")
        ).scalar(),
        "police": connexion.execute(text("SELECT id FROM police_collective ORDER BY id LIMIT 1")).scalar(),
        "compagnie": connexion.execute(text("SELECT id FROM compagnie ORDER BY id LIMIT 1")).scalar(),
    }
    # Un appel **qui ne porte pas encore de commission** : `uq_commission_appel_id` refuserait une
    # seconde commission sur le meme appel, et le refus porterait alors le nom de cette unicite au
    # lieu de celui de la contrainte visee.
    ligne = connexion.execute(
        text(
            "SELECT a.id, c.produit_id FROM appel_cotisation a"
            " JOIN contrat c ON c.id = a.contrat_id"
            " WHERE NOT EXISTS (SELECT 1 FROM commission k WHERE k.appel_id = a.id)"
            " ORDER BY a.id LIMIT 1"
        )
    ).first()
    if ligne is not None:
        cles["appel"], cles["produit"] = ligne
    manquantes = sorted(nom for nom in ("contrat", "police", "compagnie") if cles.get(nom) is None)
    if ligne is None:
        manquantes.append("appel_cotisation")
    if manquantes:
        raise SystemExit(
            "la base ne contient pas de quoi éprouver les contraintes, références absentes : "
            + ", ".join(manquantes)
            + ". Lancer `courtage generer` ou `scripts/preuve_reproductibilite.py` d'abord."
        )
    return cles


def _tentatives(cles: dict[str, int]) -> tuple[Tentative, ...]:
    """Compose les écritures interdites à partir de clés réellement présentes en base."""
    appel = INSERTION_APPEL.format
    commission = INSERTION_COMMISSION.format
    commun = {"appel": cles["appel"], "compagnie": cles["compagnie"], "produit": cles["produit"]}
    return (
        Tentative(
            regle="un appel s'adresse à un contrat ou à une police, jamais aux deux",
            contrainte="ck_appel_cotisation_destinataire_unique",
            sql=appel(
                reference="AP-INTERDIT-DEUX", contrat=cles["contrat"], police=cles["police"], affilies=1
            ),
            pourquoi=(
                "un appel portant les deux porteurs serait quittancé deux fois, une fois sur la fiche du"
                " contrat individuel et une fois sur la police collective"
            ),
        ),
        Tentative(
            regle="un appel s'adresse à un porteur, jamais à aucun",
            contrainte="ck_appel_cotisation_destinataire_unique",
            sql=appel(reference="AP-INTERDIT-AUCUN", contrat="NULL", police="NULL", affilies=1),
            pourquoi=(
                "un appel sans porteur n'est rattachable à personne, ni au quittancement ni au"
                " rapprochement bancaire"
            ),
        ),
        Tentative(
            regle="un appel couvre au moins un affilié",
            contrainte="ck_appel_cotisation_au_moins_un_affilie",
            sql=appel(reference="AP-INTERDIT-ZERO", contrat="NULL", police=cles["police"], affilies=0),
            pourquoi="un appel groupé à zéro affilié fausse la cotisation moyenne par tête des bordereaux",
        ),
        Tentative(
            regle="une commission porte le même porteur unique que l'appel qu'elle rémunère",
            contrainte="ck_commission_destinataire_unique",
            sql=commission(contrat=cles["contrat"], police=cles["police"], **commun),
            pourquoi="une commission à deux porteurs serait comptée deux fois dans le bordereau de l'apporteur",
        ),
        Tentative(
            regle="une commission porte un porteur, jamais aucun",
            contrainte="ck_commission_destinataire_unique",
            sql=commission(contrat="NULL", police="NULL", **commun),
            pourquoi="une commission sans porteur ne se rattache à aucune affaire, donc à aucun apporteur",
        ),
    )


def main() -> int:
    moteur = cree_moteur()
    nom_moteur = moteur.dialect.name
    with moteur.connect() as connexion:
        cles = _cles(connexion)
    tentatives = _tentatives(cles)

    resultats: list[dict] = []
    echecs = 0
    for tentative in tentatives:
        with moteur.connect() as connexion:
            transaction = connexion.begin()
            try:
                connexion.execute(text(tentative.sql))
            except DatabaseError as erreur:
                message = str(erreur.orig if erreur.orig is not None else erreur).strip()
                premiere_ligne = message.splitlines()[0] if message else ""
                nomme = tentative.contrainte in message
                if nomme:
                    print(f"  refusée par {tentative.contrainte} : {tentative.regle}")
                else:
                    echecs += 1
                    print(
                        f"  REFUS SANS LE BON NOM : {tentative.regle}\n"
                        f"    contrainte attendue : {tentative.contrainte}\n"
                        f"    message du moteur   : {premiere_ligne}"
                    )
                resultats.append(
                    {
                        "regle": tentative.regle,
                        "contrainte": tentative.contrainte,
                        "refusee": True,
                        "contrainte_nommee_par_le_moteur": nomme,
                        "message_du_moteur": premiere_ligne,
                        "pourquoi_la_regle_compte": tentative.pourquoi,
                    }
                )
            else:
                echecs += 1
                print(f"  ACCEPTÉE ALORS QU'ELLE VIOLE LA RÈGLE : {tentative.regle}")
                resultats.append(
                    {
                        "regle": tentative.regle,
                        "contrainte": tentative.contrainte,
                        "refusee": False,
                        "contrainte_nommee_par_le_moteur": False,
                        "message_du_moteur": None,
                        "pourquoi_la_regle_compte": tentative.pourquoi,
                    }
                )
            finally:
                transaction.rollback()

    rapport = {
        "mesure_le": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moteur": nom_moteur,
        "tentatives": len(tentatives),
        "echecs": echecs,
        "conforme": echecs == 0,
        "resultats": resultats,
    }
    chemin = RACINE_PROJET / "results" / f"contraintes_{nom_moteur}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    if echecs:
        print(
            f"NON CONFORME sur {nom_moteur} : {echecs} écriture(s) interdite(s) sur {len(tentatives)}"
            " ne sont pas refusées par la base"
        )
    else:
        print(
            f"CONFORME sur {nom_moteur} : les {len(tentatives)} écritures interdites sont refusées par la"
            " base, et le moteur nomme la contrainte"
        )
    print(f"rapport : {chemin}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
