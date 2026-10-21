"""Genere le projet Power BI versionnable `powerbi/Pilotage-Courtage.pbip` (modele TMDL + rapport).

Le modele semantique est decrit en TMDL (texte, diffable). Les mesures sont lues dans
`powerbi/mesures.dax` : il n'y a qu'une seule definition des mesures dans le depot. Les tables sont
chargees depuis les CSV produits par `scripts/exporter_marts_powerbi.py`, via le parametre de requete
`DossierDonnees` (Power BI n'accepte pas de chemin relatif : a adapter apres un clone, par
Transformer les donnees > Gerer les parametres, ou en relancant ce script avec --dossier-donnees).

Usage : python -m uv run python scripts/construire_pbip.py [--dossier-donnees "C:\\chemin\\powerbi\\donnees"]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import uuid
from pathlib import Path

_COMPTEUR = [0]


def identifiant_stable() -> uuid.UUID:
    """Identifiant deterministe : deux executions donnent les memes fichiers, donc un diff git lisible."""
    _COMPTEUR[0] += 1
    return uuid.uuid5(uuid.NAMESPACE_URL, f"courtage-erp/pbip/{_COMPTEUR[0]}")


RACINE = Path(__file__).resolve().parents[1]
POWERBI = RACINE / "powerbi"
NOM = "Pilotage-Courtage"
MODELE = POWERBI / f"{NOM}.SemanticModel"
RAPPORT = POWERBI / f"{NOM}.Report"

# Colonnes du modele : (nom, type TMDL, type M, resume par defaut, format eventuel, masquee)
INT, TXT, DATE, DBL, BOOL = (
    ("int64", "Int64.Type"), ("string", "type text"), ("dateTime", "type date"),
    ("double", "type number"), ("boolean", "type logical"),
)


def col(nom, type_, resume="none", format_=None, masquee=False):
    return (nom, type_[0], type_[1], resume, format_, masquee)


COLONNES = {
    "dim_date": [
        col("date_jour", DATE, format_="dd/mm/yyyy"), col("annee", INT, format_="0"), col("trimestre", INT, format_="0"),
        col("mois", INT, format_="0"), col("annee_mois", TXT), col("annee_trimestre", TXT),
        col("est_dernier_jour_du_mois", BOOL, masquee=True),
    ],
    "dim_produit": [
        col("produit_id", INT, masquee=True), col("code_produit", TXT), col("libelle_produit", TXT),
        col("gestion_prestations_deleguee", BOOL),
    ],
    "dim_branche": [col("branche_id", INT, masquee=True), col("code_branche", TXT), col("libelle_branche", TXT)],
    "dim_compagnie": [col("compagnie_id", INT, masquee=True), col("code_compagnie", TXT), col("raison_sociale", TXT)],
    "dim_apporteur": [
        col("apporteur_id", INT, masquee=True), col("code_apporteur", TXT), col("nom_apporteur", TXT),
        col("type_apporteur", TXT),
    ],
    "dim_adherent": [
        col("adherent_id", INT, masquee=True), col("numero_adherent", TXT), col("sexe", TXT),
        col("departement", TXT), col("type_couverture", TXT), col("tranche_age", TXT),
    ],
    "fct_cotisations": [
        col("appel_id", INT, masquee=True), col("date_echeance", DATE, format_="dd/mm/yyyy"),
        col("produit_id", INT, masquee=True), col("compagnie_id", INT, masquee=True),
        col("branche_id", INT, masquee=True), col("apporteur_id", INT, masquee=True),
        col("cotisation_ht_euros", DBL, "sum", "#,0.00 €"),
    ],
    "fct_cotisations_acquises": [
        col("appel_id", INT, masquee=True), col("mois_acquisition", DATE, format_="dd/mm/yyyy"),
        col("produit_id", INT, masquee=True), col("compagnie_id", INT, masquee=True),
        col("branche_id", INT, masquee=True), col("apporteur_id", INT, masquee=True),
        col("cotisation_acquise_ht_euros", DBL, "sum", "#,0.00 €"),
    ],
    "fct_prestations": [
        col("prestation_id", INT, masquee=True), col("date_soins", DATE, format_="dd/mm/yyyy"),
        col("date_reglement", DATE, format_="dd/mm/yyyy"), col("statut_prestation", TXT),
        col("produit_id", INT, masquee=True), col("compagnie_id", INT, masquee=True),
        col("branche_id", INT, masquee=True), col("apporteur_id", INT, masquee=True),
        col("adherent_id", INT, masquee=True), col("demande_euros", DBL, "sum", "#,0.00 €"),
        col("rembourse_euros", DBL, "sum", "#,0.00 €"),
    ],
    "fct_mouvements_portefeuille": [
        col("mouvement_id", TXT, masquee=True), col("type_mouvement", TXT),
        col("date_mouvement", DATE, format_="dd/mm/yyyy"), col("date_effet_contrat", DATE, format_="dd/mm/yyyy"),
        col("motif_resiliation", TXT), col("tranche_age_au_mouvement", TXT), col("anciennete_en_mois", INT),
        col("produit_id", INT, masquee=True), col("compagnie_id", INT, masquee=True),
        col("branche_id", INT, masquee=True), col("apporteur_id", INT, masquee=True),
        col("adherent_id", INT, masquee=True), col("cotisation_annualisee_euros", DBL, "sum", "#,0.00 €"),
    ],
    "fct_portefeuille_mensuel": [
        col("date_cliche", DATE, format_="dd/mm/yyyy"), col("contrat_id", INT, masquee=True),
        col("statut_contrat", TXT), col("produit_id", INT, masquee=True), col("compagnie_id", INT, masquee=True),
        col("branche_id", INT, masquee=True), col("apporteur_id", INT, masquee=True),
        col("adherent_id", INT, masquee=True), col("cotisation_mensuelle_euros", DBL, "sum", "#,0.00 €"),
        col("cotisation_annualisee_euros", DBL, "sum", "#,0.00 €"),
    ],
}

DESCRIPTIONS = {
    "dim_date": "Table de dates, du premier avenant a la fin de l'historique. Cle : date_jour.",
    "dim_produit": "Produit. gestion_prestations_deleguee delimite le perimetre du ratio sinistres sur primes.",
    "dim_branche": "Branche : sante individuelle, sante collective, prevoyance.",
    "dim_compagnie": "Compagnie d'assurance porteuse du risque.",
    "dim_apporteur": "Apporteur d'affaires du reseau de distribution.",
    "dim_adherent": "Adherent : departement et tranche d'age a la date d'arret. Aucune donnee nominative.",
    "fct_cotisations": "Cotisations EMISES, une ligne par appel, rattachees a la date d'echeance.",
    "fct_cotisations_acquises": "Cotisations ACQUISES, une ligne par appel et par mois couvert (cle : premier jour du mois).",
    "fct_prestations": "Prestations, une ligne par remboursement. Relation active : date de reglement.",
    "fct_mouvements_portefeuille": "Affaires nouvelles et resiliations, une ligne par mouvement.",
    "fct_portefeuille_mensuel": "Portefeuille a chaque fin de mois (un stock : ne s'additionne pas dans le temps).",
}

# (table fait, colonne fait, table dimension, colonne dimension, active)
RELATIONS = [
    ("fct_cotisations", "date_echeance", "dim_date", "date_jour", True),
    ("fct_cotisations_acquises", "mois_acquisition", "dim_date", "date_jour", True),
    ("fct_prestations", "date_reglement", "dim_date", "date_jour", True),
    ("fct_prestations", "date_soins", "dim_date", "date_jour", False),
    ("fct_mouvements_portefeuille", "date_mouvement", "dim_date", "date_jour", True),
    ("fct_portefeuille_mensuel", "date_cliche", "dim_date", "date_jour", True),
]
for _fait in ("fct_cotisations", "fct_cotisations_acquises", "fct_prestations", "fct_mouvements_portefeuille",
              "fct_portefeuille_mensuel"):
    RELATIONS += [
        (_fait, "produit_id", "dim_produit", "produit_id", True),
        (_fait, "compagnie_id", "dim_compagnie", "compagnie_id", True),
        (_fait, "branche_id", "dim_branche", "branche_id", True),
        (_fait, "apporteur_id", "dim_apporteur", "apporteur_id", True),
    ]
for _fait in ("fct_prestations", "fct_mouvements_portefeuille", "fct_portefeuille_mensuel"):
    RELATIONS.append((_fait, "adherent_id", "dim_adherent", "adherent_id", True))


def lire_mesures() -> list[dict]:
    """Extrait nom, expression, description, dossier et format de chaque bloc de powerbi/mesures.dax."""
    texte = (POWERBI / "mesures.dax").read_text(encoding="utf-8").replace("\r\n", "\n")
    mesures = []
    for bloc in re.split(r"\n\s*\n", texte):
        lignes = bloc.strip("\n").split("\n")
        description, dossier, format_, corps, nom = [], None, None, [], None
        for ligne in lignes:
            brut = ligne.strip()
            if nom is None and brut.startswith("//"):
                contenu = brut[2:].strip()
                if contenu.startswith("@dossier:"):
                    dossier = contenu.split(":", 1)[1].strip()
                elif contenu.startswith("@format:"):
                    format_ = contenu.split(":", 1)[1].strip()
                elif contenu and not set(contenu) <= {"="}:
                    description.append(contenu)
                continue
            correspondance = re.match(r"^\[(?P<nom>[^\]]+)\] =\s*(?P<reste>.*)$", brut) if nom is None else None
            if correspondance:
                nom = correspondance.group("nom")
                if correspondance.group("reste"):
                    corps.append(correspondance.group("reste"))
            elif nom is not None:
                corps.append(ligne.rstrip())
        if nom:
            mesures.append({"nom": nom, "expression": corps, "description": description,
                            "dossier": dossier, "format": format_})
    return mesures


def nom_tmdl(nom: str) -> str:
    """Identifiant TMDL entre apostrophes ; une apostrophe interne se double."""
    return "'" + nom.replace("'", "''") + "'"


def tmdl_mesure(mesure: dict) -> str:
    sortie = [f"\t/// {ligne}" for ligne in mesure["description"]]
    corps = mesure["expression"]
    if len(corps) == 1:
        sortie.append(f"\tmeasure {nom_tmdl(mesure['nom'])} = {corps[0].strip()}")
    else:
        sortie.append(f"\tmeasure {nom_tmdl(mesure['nom'])} =")
        sortie += [f"\t\t\t{ligne}" for ligne in corps]
    if mesure["format"]:
        sortie.append(f"\t\tformatString: {mesure['format']}")
    if mesure["dossier"]:
        sortie.append(f"\t\tdisplayFolder: {mesure['dossier']}")
    sortie.append(f"\t\tlineageTag: {identifiant_stable()}")
    return "\n".join(sortie) + "\n"


def tmdl_colonnes(table: str) -> str:
    morceaux = []
    for nom, type_tmdl, _type_m, resume, format_, masquee in COLONNES[table]:
        bloc = [f"\tcolumn {nom}", f"\t\tdataType: {type_tmdl}"]
        if masquee:
            bloc.append("\t\tisHidden")
        if table == "dim_date" and nom == "date_jour":
            bloc.append("\t\tisKey")
        if format_:
            bloc.append(f"\t\tformatString: {format_}")
        bloc += [f"\t\tlineageTag: {identifiant_stable()}", f"\t\tsummarizeBy: {resume}", f"\t\tsourceColumn: {nom}"]
        morceaux.append("\n".join(bloc) + "\n")
    return "\n".join(morceaux)


def tmdl_partition(table: str) -> str:
    transformations = ", ".join(f'{{"{nom}", {type_m}}}' for nom, _t, type_m, _r, _f, _m in COLONNES[table])
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(DossierDonnees & "\\{table}.csv"), '
        '[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "    Entetes = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f'    Types = Table.TransformColumnTypes(Entetes, {{{transformations}}}, "en-US")',
        "in",
        "    Types",
    ]
    corps = "\n".join(f"\t\t\t\t{ligne}" for ligne in m)
    return f"\tpartition {table} = m\n\t\tmode: import\n\t\tsource =\n{corps}\n\n"


def ecrire_modele(dossier_donnees: str) -> list[dict]:
    definition = MODELE / "definition"
    tables = definition / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    (MODELE / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOM},
        "config": {"version": "2.0", "logicalId": str(identifiant_stable())},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (MODELE / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0",
        "settings": {},
    }, indent=2), encoding="utf-8")
    (definition / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1550\n", encoding="utf-8")
    (definition / "expressions.tmdl").write_text(
        "/// Dossier contenant les CSV produits par scripts/exporter_marts_powerbi.py.\n"
        "/// Apres un clone, adapter ce parametre au chemin local du dossier powerbi/donnees.\n"
        f'expression DossierDonnees = "{dossier_donnees}" meta [IsParameterQuery=true, Type="Text", '
        "IsParameterQueryRequired=true]\n"
        f"\tlineageTag: {identifiant_stable()}\n\n\tannotation PBI_ResultType = Text\n",
        encoding="utf-8",
    )
    refs = "".join(f"ref table {table}\n" for table in [*COLONNES, "Mesures"])
    (definition / "model.tmdl").write_text(
        "model Model\n\tculture: fr-FR\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: fr-FR\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        + refs,
        encoding="utf-8",
    )

    for table in COLONNES:
        contenu = [f"/// {DESCRIPTIONS[table]}", f"table {table}", f"\tlineageTag: {identifiant_stable()}"]
        if table == "dim_date":
            contenu.append("\tdataCategory: Time")
        contenu += ["", tmdl_colonnes(table)]
        if table == "dim_date":
            contenu.append(
                "\thierarchy Calendrier\n"
                f"\t\tlineageTag: {identifiant_stable()}\n\n"
                f"\t\tlevel Annee\n\t\t\tlineageTag: {identifiant_stable()}\n\t\t\tcolumn: annee\n\n"
                f"\t\tlevel Trimestre\n\t\t\tlineageTag: {identifiant_stable()}\n\t\t\tcolumn: annee_trimestre\n\n"
                f"\t\tlevel Mois\n\t\t\tlineageTag: {identifiant_stable()}\n\t\t\tcolumn: annee_mois\n"
            )
        contenu.append(tmdl_partition(table))
        (tables / f"{table}.tmdl").write_text("\n".join(contenu), encoding="utf-8")

    mesures = lire_mesures()
    bloc = ["/// Table technique qui porte les mesures (aucune donnee).", "table Mesures",
            f"\tlineageTag: {identifiant_stable()}", ""]
    bloc += [tmdl_mesure(m) for m in mesures]
    bloc.append(
        "\tcolumn Value\n\t\tisHidden\n\t\tformatString: 0\n"
        f"\t\tlineageTag: {identifiant_stable()}\n\t\tsummarizeBy: none\n\t\tsourceColumn: [Value]\n\n"
        "\t\tannotation SummarizationSetBy = Automatic\n\n"
        "\tpartition Mesures = calculated\n\t\tmode: import\n\t\tsource = ROW(\"Value\", 0)\n"
    )
    (tables / "Mesures.tmdl").write_text("\n".join(bloc), encoding="utf-8")

    blocs = []
    for fait, colonne_fait, dim, colonne_dim, active in RELATIONS:
        lignes = [f"relationship {identifiant_stable()}"]
        if not active:
            lignes.append("\tisActive: false")
        lignes += [f"\tfromColumn: {fait}.{colonne_fait}", f"\ttoColumn: {dim}.{colonne_dim}"]
        blocs.append("\n".join(lignes) + "\n")
    (definition / "relationships.tmdl").write_text("\n".join(blocs), encoding="utf-8")
    print(f"modele : {len(mesures)} mesures, {len(COLONNES)} tables, {len(RELATIONS)} relations")
    return mesures


# --- Rapport -----------------------------------------------------------------------------------------

def _position(x, y, largeur, hauteur):
    return [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": largeur, "height": hauteur}}]


def _titre(titre):
    return {"title": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "text": {"expr": {"Literal": {"Value": f"'{titre}'"}}},
    }}]}


def _mesure(nom):
    return {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": nom}, "Name": f"Mesures.{nom}"}


def _colonne(entite, colonne, source="d"):
    return {"Column": {"Expression": {"SourceRef": {"Source": source}}, "Property": colonne},
            "Name": f"{entite}.{colonne}"}


def _conteneur(config, x, y, largeur, hauteur):
    return {"x": x, "y": y, "z": 0, "width": largeur, "height": hauteur,
            "config": json.dumps(config, ensure_ascii=False)}


def carte(mesure, x, y, largeur, hauteur, identifiant):
    config = {"name": identifiant, "layouts": _position(x, y, largeur, hauteur), "singleVisual": {
        "visualType": "card",
        "projections": {"Values": [{"queryRef": f"Mesures.{mesure}"}]},
        "prototypeQuery": {"Version": 2, "From": [{"Name": "m", "Entity": "Mesures", "Type": 0}],
                           "Select": [_mesure(mesure)]},
        "objects": {"categoryLabels": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]},
        "drillFilterOtherVisuals": True, "vcObjects": _titre(mesure)}}
    return _conteneur(config, x, y, largeur, hauteur)


def graphique(type_visuel, mesures, entite, colonne, titre, x, y, largeur, hauteur, identifiant,
              trier_par_mesure=False):
    """Graphique a une categorie et une ou plusieurs mesures (barres, colonnes, courbe)."""
    tri = ([{"Direction": 2, "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}},
                                                         "Property": mesures[0]}}}]
           if trier_par_mesure else
           [{"Direction": 1, "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                        "Property": colonne}}}])
    config = {"name": identifiant, "layouts": _position(x, y, largeur, hauteur), "singleVisual": {
        "visualType": type_visuel,
        "projections": {"Category": [{"queryRef": f"{entite}.{colonne}"}],
                        "Y": [{"queryRef": f"Mesures.{m}"} for m in mesures]},
        "prototypeQuery": {"Version": 2,
                           "From": [{"Name": "d", "Entity": entite, "Type": 0},
                                    {"Name": "m", "Entity": "Mesures", "Type": 0}],
                           "Select": [_colonne(entite, colonne), *[_mesure(m) for m in mesures]],
                           "OrderBy": tri},
        "drillFilterOtherVisuals": True, "vcObjects": _titre(titre)}}
    return _conteneur(config, x, y, largeur, hauteur)


def tableau(entite, colonne, mesures, titre, x, y, largeur, hauteur, identifiant):
    config = {"name": identifiant, "layouts": _position(x, y, largeur, hauteur), "singleVisual": {
        "visualType": "tableEx",
        "projections": {"Values": [{"queryRef": f"{entite}.{colonne}"}]
                        + [{"queryRef": f"Mesures.{m}"} for m in mesures]},
        "prototypeQuery": {"Version": 2,
                           "From": [{"Name": "d", "Entity": entite, "Type": 0},
                                    {"Name": "m", "Entity": "Mesures", "Type": 0}],
                           "Select": [_colonne(entite, colonne), *[_mesure(m) for m in mesures]],
                           "OrderBy": [{"Direction": 1, "Expression": {"Column": {
                               "Expression": {"SourceRef": {"Source": "d"}}, "Property": colonne}}}]},
        "drillFilterOtherVisuals": True, "vcObjects": _titre(titre)}}
    return _conteneur(config, x, y, largeur, hauteur)


def segment(entite, colonne, titre, x, y, largeur, hauteur, identifiant, selection=None):
    """Segment. `selection` : valeurs litterales ("2025L", "'SI'") cochees a l'ouverture du rapport."""
    visuel = {
        "visualType": "slicer",
        "projections": {"Values": [{"queryRef": f"{entite}.{colonne}"}]},
        "prototypeQuery": {"Version": 2, "From": [{"Name": "d", "Entity": entite, "Type": 0}],
                           "Select": [_colonne(entite, colonne)]},
        "drillFilterOtherVisuals": True, "vcObjects": _titre(titre)}
    if selection:
        visuel["objects"] = {"general": [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "d", "Entity": entite, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": colonne}}],
                "Values": [[{"Literal": {"Value": valeur}}] for valeur in selection]}}}],
        }}}}]}
    config = {"name": identifiant, "layouts": _position(x, y, largeur, hauteur), "singleVisual": visuel}
    return _conteneur(config, x, y, largeur, hauteur)


# Filtre de rapport : annee >= 2024. Le quittancement ne commence qu'en octobre 2023, donc un ratio calcule
# sur 2023 ou avant n'a pas de denominateur (voir docs/kpi.md). Sans ce filtre, les cartes affichent un
# ratio sur toute l'histoire, qui n'a aucun sens.
FILTRE_ANNEE_MINIMALE = {
    "name": "filtreAnneeMinimale",
    "expression": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_date"}}, "Property": "annee"}},
    "type": "Advanced",
    "filter": {
        "Version": 2,
        "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
        "Where": [{"Condition": {"Comparison": {
            "ComparisonKind": 2,
            "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "annee"}},
            "Right": {"Literal": {"Value": "2024L"}}}}}],
    },
    "howCreated": 0,
}


def pages() -> list[tuple[str, str, list[dict]]]:
    """(nom technique, titre affiche, visuels). Mise en page decrite dans docs/powerbi-maquette.md."""
    def filtres(prefixe, branche=True):
        visuels = [segment("dim_date", "annee", "Année", 1100, 16, 164, 150, f"{prefixe}SegAnnee", ["2025L"])]
        if branche:
            visuels.append(segment("dim_branche", "libelle_branche", "Branche", 1100, 176, 164, 150, f"{prefixe}SegBranche"))
        return visuels

    synthese = [
        carte("Ratio sinistres sur primes", 16, 16, 255, 110, "synSP"),
        carte("Taux de résiliation", 283, 16, 255, 110, "synRes"),
        carte("Affaires nouvelles", 550, 16, 255, 110, "synAff"),
        carte("Contrats au portefeuille", 817, 16, 255, 110, "synPtf"),
        graphique("lineChart", ["Ratio sinistres sur primes"], "dim_date", "annee_trimestre",
                  "Ratio sinistres sur primes par trimestre", 16, 140, 520, 280, "synCourbeSP"),
        graphique("columnChart", ["Affaires nouvelles", "Résiliations toutes"], "dim_date", "annee_trimestre",
                  "Entrées et sorties du portefeuille par trimestre", 548, 140, 524, 280, "synFlux"),
        graphique("columnChart", ["Contrats au portefeuille"], "dim_branche", "libelle_branche",
                  "Contrats au portefeuille par branche", 16, 434, 520, 270, "synBranche"),
        tableau("dim_date", "annee", ["Ratio sinistres sur primes", "Taux de résiliation", "Affaires nouvelles",
                                       "Contrats au portefeuille"], "Les quatre indicateurs par année",
                548, 434, 524, 270, "synTableau"),
        *filtres("syn"),
    ]
    sinistres = [
        carte("Ratio sinistres sur primes", 16, 16, 255, 110, "spCarte"),
        carte("Prestations réglées périmètre délégué", 283, 16, 255, 110, "spPrest"),
        carte("Cotisations acquises HT périmètre délégué", 550, 16, 255, 110, "spAcq"),
        carte("Contrôle ratio sur cotisations émises", 817, 16, 255, 110, "spEmises"),
        graphique("columnChart", ["Prestations réglées périmètre délégué", "Cotisations acquises HT périmètre délégué"],
                  "dim_date", "annee", "Prestations réglées et cotisations acquises par année",
                  16, 140, 520, 280, "spColonnes"),
        graphique("lineChart", ["Ratio sinistres sur primes", "Contrôle ratio en date de soins"], "dim_date",
                  "annee_trimestre", "Ratio par trimestre : date de règlement et date de soins",
                  548, 140, 524, 280, "spCourbes"),
        tableau("dim_branche", "libelle_branche", ["Prestations réglées périmètre délégué",
                                                    "Cotisations acquises HT périmètre délégué",
                                                    "Ratio sinistres sur primes"],
                "Ratio par branche", 16, 434, 520, 270, "spBranche"),
        tableau("dim_compagnie", "raison_sociale", ["Prestations réglées périmètre délégué",
                                                     "Cotisations acquises HT périmètre délégué",
                                                     "Ratio sinistres sur primes"],
                "Ratio par compagnie", 548, 434, 524, 270, "spCompagnie"),
        *filtres("sp", branche=True),
    ]
    resiliations = [
        carte("Taux de résiliation", 16, 16, 255, 110, "reCarte"),
        carte("Taux de résiliation annualisé", 283, 16, 255, 110, "reAnn"),
        carte("Résiliations de la cohorte", 550, 16, 255, 110, "reNb"),
        carte("Contrats au portefeuille en début de période", 817, 16, 255, 110, "reDebut"),
        graphique("columnChart", ["Résiliations de la cohorte"], "fct_mouvements_portefeuille", "motif_resiliation",
                  "Résiliations par motif", 16, 140, 520, 280, "reMotif", trier_par_mesure=True),
        graphique("columnChart", ["Résiliations de la cohorte"], "fct_mouvements_portefeuille",
                  "tranche_age_au_mouvement", "Résiliations par tranche d'âge au moment de la résiliation",
                  548, 140, 524, 280, "reAge"),
        tableau("dim_date", "annee", ["Résiliations de la cohorte", "Résiliations toutes",
                                       "Contrats au portefeuille en début de période", "Taux de résiliation",
                                       "Taux de résiliation annualisé"], "Taux de résiliation par année",
                16, 434, 520, 270, "reAnnees"),
        tableau("dim_produit", "libelle_produit", ["Résiliations de la cohorte",
                                                    "Contrats au portefeuille en début de période",
                                                    "Taux de résiliation"], "Taux de résiliation par produit",
                548, 434, 524, 270, "reProduit"),
        *filtres("re"),
    ]
    production = [
        carte("Affaires nouvelles", 16, 16, 255, 110, "prAff"),
        carte("Cotisation annualisée des affaires nouvelles", 283, 16, 255, 110, "prCot"),
        carte("Cotisation annualisée moyenne par affaire", 550, 16, 255, 110, "prMoy"),
        carte("Variation nette du portefeuille", 817, 16, 255, 110, "prNet"),
        graphique("barChart", ["Cotisation annualisée des affaires nouvelles"], "dim_apporteur", "nom_apporteur",
                  "Cotisation annualisée des affaires nouvelles par apporteur", 16, 140, 520, 564, "prBarres",
                  trier_par_mesure=True),
        tableau("dim_apporteur", "nom_apporteur", ["Affaires nouvelles", "Cotisation annualisée des affaires nouvelles",
                                                    "Cotisation annualisée moyenne par affaire", "Part de la production"],
                "Production par apporteur", 548, 140, 524, 400, "prTableau"),
        graphique("columnChart", ["Affaires nouvelles"], "dim_date", "annee_mois", "Affaires nouvelles par mois",
                  548, 552, 524, 152, "prMois"),
        *filtres("pr"),
    ]
    portefeuille = [
        carte("Contrats au portefeuille", 16, 16, 255, 110, "poCtr"),
        carte("Cotisation annualisée du portefeuille", 283, 16, 255, 110, "poCot"),
        carte("dont suspendus", 550, 16, 255, 110, "poSusp"),
        carte("Cotisation annualisée moyenne par contrat", 817, 16, 255, 110, "poMoy"),
        graphique("barChart", ["Cotisation annualisée du portefeuille"], "dim_branche", "libelle_branche",
                  "Cotisation annualisée par branche", 16, 140, 520, 280, "poBarres"),
        graphique("lineChart", ["Contrats au portefeuille"], "dim_date", "annee_mois",
                  "Contrats au portefeuille à chaque fin de mois", 548, 140, 524, 280, "poCourbe"),
        tableau("dim_branche", "libelle_branche", ["Contrats au portefeuille", "dont suspendus",
                                                    "Cotisation annualisée du portefeuille",
                                                    "Cotisation annualisée moyenne par contrat"],
                "Portefeuille par branche", 16, 434, 520, 270, "poTableau"),
        tableau("dim_adherent", "tranche_age", ["Contrats au portefeuille", "Cotisation annualisée du portefeuille"],
                "Portefeuille par tranche d'âge de l'adhérent", 548, 434, 524, 270, "poAge"),
        segment("dim_date", "annee", "Année", 1100, 16, 164, 150, "poSegAnnee", ["2025L"]),
        segment("dim_adherent", "departement", "Département", 1100, 176, 164, 150, "poSegDep"),
    ]
    return [
        ("pageSynthese", "Synthèse", synthese),
        ("pageSinistres", "Sinistres sur primes", sinistres),
        ("pageResiliations", "Résiliations", resiliations),
        ("pageProduction", "Production par apporteur", production),
        ("pagePortefeuille", "Portefeuille par branche", portefeuille),
    ]


def ecrire_rapport() -> None:
    RAPPORT.mkdir(parents=True, exist_ok=True)
    (RAPPORT / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NOM},
        "config": {"version": "2.0", "logicalId": str(identifiant_stable())},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAPPORT / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../{NOM}.SemanticModel"}},
    }, indent=2), encoding="utf-8")

    sections = []
    nombre_visuels = 0
    for ordre, (nom, titre, visuels) in enumerate(pages()):
        nombre_visuels += len(visuels)
        sections.append({"config": "{}", "displayName": titre, "displayOption": 1, "filters": "[]",
                         "height": 720.0, "name": nom, "ordinal": ordre, "visualContainers": visuels,
                         "width": 1280.0})
    rapport = {
        "config": json.dumps({
            "version": "5.55",
            "themeCollection": {"baseTheme": {"name": "CY24SU10", "version": "5.55", "type": 2}},
            "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
            "settings": {"useStylableVisualContainerHeader": True},
        }, ensure_ascii=False),
        "filters": json.dumps([FILTRE_ANNEE_MINIMALE], ensure_ascii=False),
        "layoutOptimization": 0,
        "resourcePackages": [{"resourcePackage": {
            "disabled": False,
            "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": 202}],
            "name": "SharedResources", "type": 2}}],
        "sections": sections,
    }
    (RAPPORT / "report.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rapport : {len(sections)} pages, {nombre_visuels} visuels")


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--dossier-donnees", default=r"C:\cheminers\courtage-erp\powerbi\donnees",
                         help="chemin absolu du dossier powerbi/donnees sur ce poste")
    args = parseur.parse_args()

    _COMPTEUR[0] = 0
    for dossier in (MODELE, RAPPORT):
        if dossier.exists():
            shutil.rmtree(dossier)
    POWERBI.mkdir(exist_ok=True)
    (POWERBI / f"{NOM}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NOM}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, indent=2), encoding="utf-8")
    ecrire_modele(args.dossier_donnees)
    ecrire_rapport()
    print(f"projet : {(POWERBI / f'{NOM}.pbip').relative_to(RACINE).as_posix()}")


if __name__ == "__main__":
    main()
