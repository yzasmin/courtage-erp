"""Agent de pre-remplissage (module 4a) : controles, validation humaine et mode hors ligne.

Ces tests n'appellent jamais le modele. Les controles et la validation se testent sur des champs
construits a la main ; le mode hors ligne, sur une reponse enregistree ecrite par le test. La precision
reelle de l'extraction est mesuree a part, par `courtage ia evaluer`, et verrouillee par le dernier test
quand les reponses enregistrees sont presentes.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from courtage.ia import extraction, traitement
from courtage.ia.extraction import ChampsExtraits
from courtage.modeles import DossierPreRempli, StatutDossier
from courtage.modeles.financier import Prestation
from courtage.services import contrats as service_contrats

DATE_EFFET = date(2024, 3, 1)
DATE_SOINS = date(2025, 5, 12)


def _champs(contrat, **modifications) -> ChampsExtraits:
    valeurs = {
        "type_document": "demande_remboursement",
        "numero_adherent": "A999001",
        "nom": "TEISSIER",
        "prenom": "Camille",
        "numero_contrat": contrat.numero_contrat,
        "date_document": DATE_SOINS,
        "emetteur": "Cabinet Grossiste Delegataire",
        "code_garantie": "SOINS",
        "montant_total_cents": 9000,
        "lignes": [
            {"libelle": "Consultation medecin generaliste", "montant_cents": 3000},
            {"libelle": "Consultation specialiste", "montant_cents": 6000},
        ],
    }
    valeurs.update(modifications)
    return ChampsExtraits.model_validate(valeurs)


def _reponse(champs: ChampsExtraits) -> extraction.Reponse:
    return extraction.Reponse(champs=champs, modele="test", jetons_entree=500, jetons_sortie=150, latence_ms=900)


@pytest.fixture
def contrat_en_vigueur(session, contrat_oceane):
    service_contrats.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    return contrat_oceane


def _niveaux(controles) -> dict[str, str]:
    return {c.code: c.niveau for c in controles}


def test_un_document_conforme_ne_porte_aucun_controle_bloquant(session, contrat_en_vigueur) -> None:
    controles, adherent, contrat, similarite = traitement.controle(session, _champs(contrat_en_vigueur))
    assert all(c.niveau == "ok" for c in controles), controles
    assert adherent.numero_adherent == "A999001"
    assert contrat.id == contrat_en_vigueur.id
    assert similarite == 1.0


def test_un_nom_approchant_est_signale_avec_l_ecart_et_non_corrige(session, contrat_en_vigueur) -> None:
    controles, *_ = traitement.controle(session, _champs(contrat_en_vigueur, nom="TEISSSIER"))
    nom = next(c for c in controles if c.code == "nom")
    assert nom.niveau == "alerte"
    assert "TEISSSIER" in nom.message and "Teissier" in nom.message


@pytest.mark.parametrize(
    ("modification", "code"),
    [
        ({"numero_adherent": "A900000"}, "adherent"),
        ({"montant_total_cents": 10000}, "montants"),
        ({"date_document": date(2023, 1, 5)}, "garantie_a_date"),
        ({"numero_contrat": "SI-1999-99999"}, "contrat"),
    ],
)
def test_les_anomalies_bloquent_la_validation(session, contrat_en_vigueur, modification, code) -> None:
    controles, *_ = traitement.controle(session, _champs(contrat_en_vigueur, **modification))
    assert _niveaux(controles)[code] == "bloquant"


def test_une_compagnie_qui_ne_delegue_pas_les_prestations_bloque_le_dossier(session, contrat_prevoyance) -> None:
    service_contrats.met_en_vigueur(session, contrat_prevoyance, DATE_EFFET)
    controles, *_ = traitement.controle(session, _champs(contrat_prevoyance))
    assert _niveaux(controles)["delegation"] == "bloquant"


def test_le_dossier_nait_a_valider_et_n_ecrit_aucune_prestation(session, contrat_en_vigueur) -> None:
    avant = session.scalar(select(Prestation.id).order_by(Prestation.id.desc()))
    dossier = traitement.cree_dossier(session, "essai-1.pdf", _reponse(_champs(contrat_en_vigueur)))
    assert dossier.statut is StatutDossier.A_VALIDER
    assert dossier.prestation_id is None
    assert session.scalar(select(Prestation.id).order_by(Prestation.id.desc())) == avant


def test_la_validation_humaine_cree_la_prestation(session, contrat_en_vigueur) -> None:
    dossier = traitement.cree_dossier(session, "essai-2.pdf", _reponse(_champs(contrat_en_vigueur)))
    traitement.valide_dossier(session, dossier)
    prestation = session.get(Prestation, dossier.prestation_id)
    assert dossier.statut is StatutDossier.VALIDE
    assert prestation.montant_demande_cents == 9000
    assert prestation.date_soins == DATE_SOINS


def test_un_dossier_bloque_ne_se_valide_pas_et_un_rejet_doit_etre_motive(session, contrat_en_vigueur) -> None:
    dossier = traitement.cree_dossier(
        session, "essai-3.pdf", _reponse(_champs(contrat_en_vigueur, montant_total_cents=12000))
    )
    with pytest.raises(traitement.DossierNonValidable):
        traitement.valide_dossier(session, dossier)
    with pytest.raises(traitement.DossierNonValidable):
        traitement.rejette_dossier(session, dossier, "  ")
    traitement.rejette_dossier(session, dossier, "Total incoherent, facture redemandee a l'opticien")
    assert dossier.statut is StatutDossier.REJETE


def test_l_ecran_de_validation_affiche_le_dossier_et_ses_controles(session, client, contrat_en_vigueur) -> None:
    traitement.cree_dossier(session, "essai-4.pdf", _reponse(_champs(contrat_en_vigueur, nom="TEISSSIER")))
    page = client.get("/dossiers-a-valider").text
    assert "essai-4.pdf" in page
    assert "nom approchant" in page
    assert "Valider et créer la prestation" in page


def test_le_mode_hors_ligne_rejoue_et_refuse_une_reponse_perimee(tmp_path: Path) -> None:
    texte = "FACTURE\nPatient : Camille TEISSIER\nTotal 90,00 EUR"
    reponse = {
        "type_document": "facture_optique", "numero_adherent": None, "nom": "TEISSIER", "prenom": "Camille",
        "numero_contrat": None, "date_document": None, "emetteur": None, "code_garantie": "OPTIQUE",
        "montant_total_cents": 9000, "lignes": [],
    }
    enregistrement = {
        "modele": extraction.MODELE,
        "empreinte_requete": extraction.empreinte_requete(texte),
        "reponse_texte": json.dumps(reponse),
        "jetons_entree": 400,
        "jetons_sortie": 120,
        "latence_ms": 800,
    }
    (tmp_path / "doc.json").write_text(json.dumps(enregistrement), encoding="utf-8")

    rejouee = extraction.extrait(texte, "doc.pdf", "enregistre", tmp_path)
    assert rejouee.champs.montant_total_cents == 9000
    assert rejouee.cout_microdollars == 100  # 400 x 0,10 + 120 x 0,50 microdollars

    with pytest.raises(extraction.ExtractionImpossible, match="perimee"):
        extraction.extrait(texte + " modifie", "doc.pdf", "enregistre", tmp_path)


DONNEES = Path(__file__).resolve().parents[1] / "data" / "ia"


@pytest.mark.skipif(
    not (DONNEES / "reponses").exists(), reason="reponses enregistrees absentes : lancer courtage ia evaluer --mode api"
)
def test_l_extraction_enregistree_ne_regresse_pas() -> None:
    """Verrou de non-regression : rejoue les 30 reponses enregistrees contre la verite terrain."""
    verites = json.loads((DONNEES / "documents" / "verite_terrain.json").read_text(encoding="utf-8"))
    justes = total = 0
    for verite in verites:
        chemin = DONNEES / "documents" / verite["fichier"]
        champs = extraction.extrait(
            extraction.texte_du_pdf(chemin), chemin.name, "enregistre", DONNEES / "reponses"
        ).champs.model_dump(mode="json")
        for champ in ("type_document", "numero_adherent", "numero_contrat", "date_document", "montant_total_cents"):
            total += 1
            justes += verite[champ] == champs[champ]
    assert justes / total >= 0.95


def test_aucun_dossier_n_est_valide_sans_decision(session) -> None:
    valides_sans_date = session.scalars(
        select(DossierPreRempli).where(
            DossierPreRempli.statut == StatutDossier.VALIDE, DossierPreRempli.decide_le.is_(None)
        )
    ).all()
    assert valides_sans_date == []
