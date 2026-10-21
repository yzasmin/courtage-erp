"""Le projet Power BI se verifie sans Power BI : coherence entre mesures, modele, rapport et requetes de controle.

Ces tests ne remplacent pas l'ouverture dans Power BI Desktop (voir docs/powerbi-maquette.md et
results/concordance_dax_sql.json), mais ils attrapent en integration continue les fautes qui feraient
echouer cette ouverture : une mesure citee qui n'existe plus, une colonne absente du modele.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def _charge_constructeur():
    spec = importlib.util.spec_from_file_location("construire_pbip", RACINE / "scripts" / "construire_pbip.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


constructeur = _charge_constructeur()


def test_chaque_mesure_a_un_nom_unique_une_definition_un_dossier_et_un_format():
    mesures = constructeur.lire_mesures()
    noms = [m["nom"] for m in mesures]
    assert len(noms) == len(set(noms))
    assert len(mesures) >= 20
    for mesure in mesures:
        assert mesure["expression"], mesure["nom"]
        assert mesure["description"], f"mesure sans commentaire : {mesure['nom']}"
        assert mesure["dossier"], f"mesure sans dossier : {mesure['nom']}"
        assert mesure["format"], f"mesure sans format : {mesure['nom']}"


def test_les_quatre_indicateurs_ont_leur_mesure_principale():
    noms = {m["nom"] for m in constructeur.lire_mesures()}
    assert {
        "Ratio sinistres sur primes",
        "Taux de résiliation",
        "Cotisation annualisée des affaires nouvelles",
        "Cotisation annualisée du portefeuille",
    } <= noms


def test_les_mesures_citees_par_le_dax_les_requetes_de_controle_et_le_rapport_existent():
    noms = {m["nom"] for m in constructeur.lire_mesures()}
    citees = set()
    for mesure in constructeur.lire_mesures():
        citees |= set(re.findall(r"(?<![A-Za-z_\]])\[([^\]]+)\]", "\n".join(mesure["expression"])))
    for fichier in (RACINE / "powerbi" / "controles").glob("*.dax"):
        citees |= set(re.findall(r"\[([^\]]+)\]", fichier.read_text(encoding="utf-8")))
    for _nom, _titre, visuels in constructeur.pages():
        for visuel in visuels:
            config = json.loads(visuel["config"])["singleVisual"]
            for selection in config["prototypeQuery"]["Select"]:
                if "Measure" in selection:
                    citees.add(selection["Measure"]["Property"])
    colonnes = {c[0] for table in constructeur.COLONNES.values() for c in table}
    inconnues = {c for c in citees if c not in noms and c not in colonnes}
    assert not inconnues, f"references a des mesures inexistantes : {sorted(inconnues)}"


def test_les_relations_portent_sur_des_colonnes_du_modele():
    colonnes = {table: {c[0] for c in specs} for table, specs in constructeur.COLONNES.items()}
    for fait, colonne_fait, dim, colonne_dim, _active in constructeur.RELATIONS:
        assert colonne_fait in colonnes[fait], (fait, colonne_fait)
        assert colonne_dim in colonnes[dim], (dim, colonne_dim)


def test_une_seule_relation_active_par_couple_de_tables():
    vues = set()
    for fait, _cf, dim, _cd, active in constructeur.RELATIONS:
        if active:
            cle = (fait, dim)
            assert cle not in vues, f"deux relations actives entre {fait} et {dim}"
            vues.add(cle)


def test_le_fichier_pbip_declare_le_bon_schema():
    pbip = RACINE / "powerbi" / "Pilotage-Courtage.pbip"
    contenu = json.loads(pbip.read_text(encoding="utf-8"))
    assert re.fullmatch(
        r"https://developer\.microsoft\.com/json-schemas/fabric/pbip/pbipProperties/1\.[0-9]+\.[0-9]+/schema\.json",
        contenu["$schema"],
    )
    assert (RACINE / "powerbi" / "Pilotage-Courtage.SemanticModel" / "definition" / "model.tmdl").exists()


def test_aucun_tiret_cadratin_dans_les_livrables_du_module_3():
    tiret = chr(0x2014)
    fichiers = [
        *RACINE.glob("sql/kpi/*.sql"), *RACINE.glob("powerbi/*.dax"), *RACINE.glob("powerbi/controles/*.dax"),
        *RACINE.glob("scripts/*kpi*"), *RACINE.glob("scripts/*pbip*"), *RACINE.glob("dbt/models/marts/*"),
        RACINE / "docs" / "kpi.md", RACINE / "docs" / "powerbi-maquette.md",
    ]
    fautifs = [f.name for f in fichiers if f.is_file() and tiret in f.read_text(encoding="utf-8")]
    assert not fautifs, fautifs
