"""Prediction de resiliation (module 5) : metriques, facteurs affiches et fiche adherent.

L'apprentissage lui-meme se rejoue avec `courtage ml entrainer` sur PostgreSQL, ou vivent les variables
construites par dbt. Ici sont verifiees les briques dont depend ce qu'un gestionnaire voit.
"""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("lightgbm", reason="option `ml` non installee")

import numpy as np
import pandas as pd

from courtage.ml import resiliation as r


def test_le_lift_du_premier_decile_rapporte_le_taux_des_plus_risques_au_taux_moyen() -> None:
    # 20 contrats, 4 resiliations dont 2 parmi les 2 scores les plus eleves : taux de 100 % dans le
    # premier decile contre 20 % en moyenne, soit un lift de 5.
    y = np.array([1, 1] + [0] * 16 + [1, 1])
    p = np.array([0.9, 0.8] + [0.1] * 18)
    resultat = r.mesures(y, p)
    assert resultat["taux_resiliation_premier_decile"] == 1.0
    assert resultat["lift_premier_decile"] == 5.0


def test_seuls_les_facteurs_qui_augmentent_le_risque_sont_affiches() -> None:
    ligne = pd.Series(
        {"revalorisation_bp": 820, "anciennete_mois": 7, "age": 66, "code_apporteur": "AP04", "nb_suspensions": 0}
    )
    contribution = pd.Series(
        {"revalorisation_bp": 0.9, "anciennete_mois": 0.4, "age": -0.5, "code_apporteur": 0.6, "nb_suspensions": 0.0}
    )
    facteurs = r.trois_facteurs(ligne, contribution)
    assert facteurs == [
        "Revalorisation de 8,2 % au dernier 1er janvier",
        "Apporté par AP04",
        "Ancienneté de 7 mois",
    ]


def test_la_fiche_adherent_affiche_le_dernier_score_et_ses_facteurs(session, client, contrat_oceane) -> None:
    from courtage.modeles import ScoreResiliation

    for mois, probabilite in ((date(2026, 8, 1), 0.12), (date(2026, 9, 1), 0.41)):
        session.add(
            ScoreResiliation(
                contrat_id=contrat_oceane.id,
                date_observation=mois,
                probabilite=probabilite,
                decile=10 if probabilite > 0.3 else 6,
                facteur_1="Revalorisation de 7,5 % au dernier 1er janvier",
                version_modele="test",
            )
        )
    session.flush()

    page = client.get("/adherents/A999001").text
    assert "41 %" in page
    assert "12 %" not in page, "seul le score le plus recent doit etre affiche"
    assert "Revalorisation de 7,5 %" in page
    assert "à contacter" in page
