"""L'alerte qui rend un lot rejeté visible dans Airflow.

La spécification du module 2 demande qu'un rejet se voie dans l'orchestrateur. Le mécanisme retenu est
une tâche terminale qui sort en code 1 quand le dépôt récent contient un lot rejeté, ce qui fait rougir
le graphe sans empêcher les lots sains d'être traités.

Ces tests existent parce que le mécanisme n'en avait aucun : la seule preuve publiée avait été produite
avec une fenêtre vide, donc elle annonçait « rien à signaler » sur une chaîne qui venait de refuser neuf
bordereaux. Une alerte que personne ne teste est une alerte dont on découvre le jour venu qu'elle ne
part pas.

Deux niveaux sont couverts séparément, parce qu'ils peuvent se tromper indépendamment : la **sélection**
des lots, qui est une question de fenêtre et d'horodatage, et le **code de retour** de la commande, qui
est ce que l'orchestrateur lit.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from courtage.flux import cli, journal
from courtage.flux.enums import FormatFichier, StatutLot, TypeFlux
from courtage.flux.modeles import LotFichier


def _lot(reference: str, statut: StatutLot, detecte_le: datetime, traite_le: datetime | None) -> LotFichier:
    return LotFichier(
        reference_lot=reference,
        nom_fichier=f"{reference}.csv",
        type_flux=TypeFlux.COTISATIONS,
        format_fichier=FormatFichier.CSV,
        sha256=reference.ljust(64, "0")[:64],
        taille_octets=1_024,
        compagnie_id=None,
        periode=date(2026, 6, 1),
        date_depot=date(2026, 7, 1),
        statut=statut,
        nombre_lignes_fichier=12,
        nombre_lignes_chargees=0,
        motif_rejet="total déclaré différent de la somme des lignes" if statut is StatutLot.REJETE else None,
        detecte_le=detecte_le,
        traite_le=traite_le,
    )


# --- Sélection des lots --------------------------------------------------------------------------


def test_un_lot_rejete_dans_la_fenetre_est_signale(session) -> None:
    """Le cas qui doit faire rougir le graphe : un bordereau refusé à l'instant."""
    maintenant = journal.debut_de_fenetre(session, heures=0)
    session.add(_lot("LOT-REJETE-RECENT", StatutLot.REJETE, maintenant, maintenant))
    session.flush()

    rejetes = journal.lots_rejetes_depuis(session, maintenant - timedelta(hours=24))

    assert [lot["reference_lot"] for lot in rejetes] == ["LOT-REJETE-RECENT"]
    assert rejetes[0]["motif_rejet"], "le motif doit accompagner le lot, c'est la pièce renvoyée"


def test_un_lot_rejete_hors_de_la_fenetre_n_est_plus_signale(session) -> None:
    """Un rejet corrigé depuis ne doit pas faire rougir le graphe indéfiniment."""
    maintenant = journal.debut_de_fenetre(session, heures=0)
    vieux = maintenant - timedelta(days=5)
    session.add(_lot("LOT-REJETE-ANCIEN", StatutLot.REJETE, vieux, vieux))
    session.flush()

    assert journal.lots_rejetes_depuis(session, maintenant - timedelta(hours=24)) == []


def test_la_fenetre_suit_la_date_de_rejet_et_non_celle_de_detection(session) -> None:
    """Un lot détecté il y a trois jours mais rejeté à l'instant doit être signalé.

    C'est le défaut que ce test ferme. La fenêtre se bornait sur `detecte_le`, et un lot dont
    l'archivage avait échoué le lundi, puis qui était rejeté le mercredi au repassage de la chaîne,
    sortait de la fenêtre du mercredi. Le bordereau était refusé, et aucune alerte ne partait.
    """
    maintenant = journal.debut_de_fenetre(session, heures=0)
    session.add(
        _lot("LOT-REJETE-TARDIF", StatutLot.REJETE, maintenant - timedelta(days=3), maintenant)
    )
    session.flush()

    rejetes = journal.lots_rejetes_depuis(session, maintenant - timedelta(hours=24))

    assert [lot["reference_lot"] for lot in rejetes] == ["LOT-REJETE-TARDIF"]


def test_un_lot_charge_n_est_jamais_signale(session) -> None:
    """Témoin. Sans lui, les tests précédents prouveraient seulement que tout est signalé."""
    maintenant = journal.debut_de_fenetre(session, heures=0)
    session.add(_lot("LOT-CHARGE", StatutLot.CHARGE, maintenant, maintenant))
    session.flush()

    assert journal.lots_rejetes_depuis(session, maintenant - timedelta(hours=24)) == []


# --- Code de retour de la commande ----------------------------------------------------------------
#
# La commande ouvre sa propre session, hors de la transaction du test : ce qui est vérifié ici est le
# verdict qu'elle tire d'une liste de rejets, et non la lecture de la base, déjà couverte ci-dessus.


def _sans_base(monkeypatch, tmp_path, rejetes: list[dict[str, object]]) -> None:
    monkeypatch.setenv("COURTAGE_RESULTATS", str(tmp_path))
    monkeypatch.setattr(journal, "lots_rejetes_depuis", lambda *_: rejetes)
    monkeypatch.setattr(journal, "debut_de_fenetre", lambda *_, **__: datetime(2026, 7, 1, 2, 0))


def test_la_commande_sort_en_echec_quand_un_lot_est_rejete(monkeypatch, tmp_path) -> None:
    _sans_base(
        monkeypatch,
        tmp_path,
        [
            {
                "reference_lot": "LOT-REJETE",
                "nom_fichier": "COTISATIONS.csv",
                "type_flux": "cotisations",
                "periode": "2026-06-01",
                "motif_rejet": "total déclaré différent de la somme des lignes",
                "rejete_le": "2026-07-02T03:00:00",
            }
        ],
    )

    assert cli.commande_alerter(argparse.Namespace(depuis=None)) == 1, (
        "c'est ce code de retour qui fait rougir la tâche dans Airflow"
    )
    assert (tmp_path / "flux_alerte_rejets.json").exists(), "le compte rendu doit être écrit malgré l'échec"


def test_la_commande_sort_en_succes_sans_rejet(monkeypatch, tmp_path) -> None:
    _sans_base(monkeypatch, tmp_path, [])

    assert cli.commande_alerter(argparse.Namespace(depuis=None)) == 0
