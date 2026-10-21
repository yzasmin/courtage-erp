"""Compare les mesures DAX evaluees par Power BI Desktop aux memes calculs recalcules en SQL.

Entrees : results/powerbi/*.csv (sorties de scripts/executer_dax.ps1, moteur Power BI, apres actualisation)
          les marts PostgreSQL (COURTAGE_BASE_URL), interroges par des requetes ecrites ici, independamment
          du DAX : pas de lecture du modele Power BI, pas de reprise de ses expressions.
Sortie  : results/concordance_dax_sql.csv, results/concordance_dax_sql.md et un resume affiche.

Usage : COURTAGE_BASE_URL=postgresql+psycopg://... python -m uv run python scripts/concordance_kpi.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text

RACINE = Path(__file__).resolve().parents[1]
DAX = RACINE / "results" / "powerbi"
ARRET = date(2026, 9, 30)  # derniere date de la table de dates, relue et verifiee plus bas

# Colonne du resultat DAX -> (cle interne, nom de la mesure dans Power BI, nature)
# nature "additive" : un BLANK DAX vaut zero ; "ratio" : un BLANK DAX est l'absence de valeur.
MESURES = {
    "Prestations delegue": ("prestations", "Prestations réglées périmètre délégué", "additive"),
    "Acquises delegue": ("acquises", "Cotisations acquises HT périmètre délégué", "additive"),
    "Emises": ("emises", "Cotisations émises HT", "additive"),
    "Ratio SP": ("ratio_sp", "Ratio sinistres sur primes", "ratio"),
    "Ratio date de soins": ("ratio_soins", "Contrôle ratio en date de soins", "ratio"),
    "Ratio sur emises": ("ratio_emises", "Contrôle ratio sur cotisations émises", "ratio"),
    "Ratio tous produits": ("ratio_tous", "Contrôle ratio tous produits", "ratio"),
    "Contrats debut": ("contrats_debut", "Contrats au portefeuille en début de période", "additive"),
    "Resiliations cohorte": ("res_cohorte", "Résiliations de la cohorte", "additive"),
    "Resiliations toutes": ("res_toutes", "Résiliations toutes", "additive"),
    "Taux resiliation": ("taux", "Taux de résiliation", "ratio"),
    "Jours": ("jours", "Jours de la période", "additive"),
    "Taux annualise": ("taux_annualise", "Taux de résiliation annualisé", "ratio"),
    "Taux sur effectif de fin": ("taux_fin", "Contrôle taux sur effectif de fin", "ratio"),
    "Affaires nouvelles": ("affaires", "Affaires nouvelles", "additive"),
    "Annualisee nouvelles": ("annualisee_nouvelles", "Cotisation annualisée des affaires nouvelles", "additive"),
    "Variation nette": ("variation", "Variation nette du portefeuille", "additive"),
    "Contrats portefeuille": ("contrats", "Contrats au portefeuille", "additive"),
    "Suspendus": ("suspendus", "dont suspendus", "additive"),
    "Annualisee portefeuille": ("annualisee_ptf", "Cotisation annualisée du portefeuille", "additive"),
    "Part": ("part", "Part de la production", "ratio"),
}


class Sql:
    """Valeurs SQL d'un contexte : une annee, une branche et un apporteur facultatifs."""

    def __init__(self, connexion):
        self.c = connexion

    def un(self, requete: str, **params):
        return self.c.execute(text(requete), params).scalar()

    def contexte(self, annee: int, branche: str | None, apporteur: str | None) -> dict:
        d0 = date(annee, 1, 1)
        d1 = min(date(annee, 12, 31), ARRET)
        veille = date(annee - 1, 12, 31)
        p = {"d0": d0, "d1": d1, "veille": veille, "b": branche, "a": apporteur}
        fb = "(cast(:b as text) is null or br.code_branche = :b)"
        fa = "(cast(:a as text) is null or ap.code_apporteur = :a)"
        m = "analytique_marts"

        prestations = self.un(f"""
            select sum(f.rembourse_euros) from {m}.fct_prestations f
            join {m}.dim_produit pr on pr.produit_id = f.produit_id and pr.gestion_prestations_deleguee
            join {m}.dim_branche br on br.branche_id = f.branche_id
            where f.statut_prestation = 'reglee' and f.date_reglement between :d0 and :d1 and {fb}""", **p)
        prestations_soins = self.un(f"""
            select sum(f.rembourse_euros) from {m}.fct_prestations f
            join {m}.dim_produit pr on pr.produit_id = f.produit_id and pr.gestion_prestations_deleguee
            join {m}.dim_branche br on br.branche_id = f.branche_id
            where f.statut_prestation = 'reglee' and f.date_soins between :d0 and :d1 and {fb}""", **p)
        acquises = self.un(f"""
            select sum(f.cotisation_acquise_ht_euros) from {m}.fct_cotisations_acquises f
            join {m}.dim_produit pr on pr.produit_id = f.produit_id and pr.gestion_prestations_deleguee
            join {m}.dim_branche br on br.branche_id = f.branche_id
            where f.mois_acquisition between :d0 and :d1 and {fb}""", **p)
        acquises_tous = self.un(f"""
            select sum(f.cotisation_acquise_ht_euros) from {m}.fct_cotisations_acquises f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            where f.mois_acquisition between :d0 and :d1 and {fb}""", **p)
        emises = self.un(f"""
            select sum(f.cotisation_ht_euros) from {m}.fct_cotisations f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            where f.date_echeance between :d0 and :d1 and {fb}""", **p)
        emises_deleguees = self.un(f"""
            select sum(f.cotisation_ht_euros) from {m}.fct_cotisations f
            join {m}.dim_produit pr on pr.produit_id = f.produit_id and pr.gestion_prestations_deleguee
            join {m}.dim_branche br on br.branche_id = f.branche_id
            where f.date_echeance between :d0 and :d1 and {fb}""", **p)

        def portefeuille(jour, statut=None):
            return self.un(f"""
                select count(*) from {m}.fct_portefeuille_mensuel f
                join {m}.dim_branche br on br.branche_id = f.branche_id
                join {m}.dim_apporteur ap on ap.apporteur_id = f.apporteur_id
                where f.date_cliche = :jour and {fb} and {fa}
                  and (cast(:statut as text) is null or f.statut_contrat = :statut)""",
                            jour=jour, statut=statut, b=branche, a=apporteur)

        debut = portefeuille(veille)
        fin = portefeuille(d1)
        res_cohorte = self.un(f"""
            select count(*) from {m}.fct_mouvements_portefeuille f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            join {m}.dim_apporteur ap on ap.apporteur_id = f.apporteur_id
            where f.type_mouvement = 'resiliation' and f.date_mouvement between :d0 and :d1
              and f.date_effet_contrat < :d0 and {fb} and {fa}""", **p)
        res_toutes = self.un(f"""
            select count(*) from {m}.fct_mouvements_portefeuille f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            join {m}.dim_apporteur ap on ap.apporteur_id = f.apporteur_id
            where f.type_mouvement = 'resiliation' and f.date_mouvement between :d0 and :d1 and {fb} and {fa}""", **p)
        affaires = self.un(f"""
            select count(*) from {m}.fct_mouvements_portefeuille f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            join {m}.dim_apporteur ap on ap.apporteur_id = f.apporteur_id
            where f.type_mouvement = 'affaire_nouvelle' and f.date_mouvement between :d0 and :d1 and {fb} and {fa}""", **p)
        annualisee_nouvelles = self.un(f"""
            select sum(f.cotisation_annualisee_euros) from {m}.fct_mouvements_portefeuille f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            join {m}.dim_apporteur ap on ap.apporteur_id = f.apporteur_id
            where f.type_mouvement = 'affaire_nouvelle' and f.date_mouvement between :d0 and :d1 and {fb} and {fa}""", **p)
        total_nouvelles = self.un(f"""
            select sum(f.cotisation_annualisee_euros) from {m}.fct_mouvements_portefeuille f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            where f.type_mouvement = 'affaire_nouvelle' and f.date_mouvement between :d0 and :d1 and {fb}""", **p)
        annualisee_ptf = self.un(f"""
            select sum(f.cotisation_annualisee_euros) from {m}.fct_portefeuille_mensuel f
            join {m}.dim_branche br on br.branche_id = f.branche_id
            join {m}.dim_apporteur ap on ap.apporteur_id = f.apporteur_id
            where f.date_cliche = :d1 and {fb} and {fa}""", **p)

        def rapport(a, b):
            return None if not b else float(a or 0) / float(b)

        jours = (d1 - d0).days + 1
        taux = rapport(res_cohorte, debut)
        return {
            "prestations": prestations, "acquises": acquises, "emises": emises,
            "ratio_sp": rapport(prestations, acquises),
            "ratio_soins": rapport(prestations_soins, acquises),
            "ratio_emises": rapport(prestations, emises_deleguees),
            "ratio_tous": rapport(prestations, acquises_tous),
            "contrats_debut": debut, "res_cohorte": res_cohorte, "res_toutes": res_toutes,
            "taux": taux, "jours": jours,
            "taux_annualise": None if taux is None else taux * 365 / jours,
            "taux_fin": rapport(res_cohorte, fin),
            "affaires": affaires, "annualisee_nouvelles": annualisee_nouvelles,
            "variation": affaires - res_toutes, "contrats": fin,
            "suspendus": portefeuille(d1, "suspendu"), "annualisee_ptf": annualisee_ptf,
            "part": rapport(annualisee_nouvelles, total_nouvelles),
        }


def main() -> int:
    url = os.environ.get("COURTAGE_BASE_URL", "")
    if not url.startswith("postgresql"):
        print("Renseigner COURTAGE_BASE_URL (PostgreSQL).", file=sys.stderr)
        return 2
    with create_engine(url).connect() as connexion:
        derniere_date = connexion.execute(text("select max(date_jour) from analytique_marts.dim_date")).scalar()
        if derniere_date != ARRET:
            print(f"Date d'arret inattendue : {derniere_date}", file=sys.stderr)
            return 1
        sql = Sql(connexion)
        resultats = []
        for _nom, fichier, cle in (("par_annee", "01_par_annee", None), ("par_annee_branche", "02_par_annee_branche", "code_branche"),
                                  ("par_annee_apporteur", "03_par_annee_apporteur", "code_apporteur")):
            with (DAX / f"{fichier}.csv").open(encoding="utf-8-sig", newline="") as f:
                for brut in csv.DictReader(f):
                    contexte = {}
                    for k, v in brut.items():
                        court = k.split("[")[-1].rstrip("]")
                        contexte[court] = v
                    annee = int(contexte["annee"])
                    branche = contexte.get("code_branche") if cle == "code_branche" else None
                    apporteur = contexte.get("code_apporteur") if cle == "code_apporteur" else None
                    valeurs_sql = sql.contexte(annee, branche, apporteur)
                    for colonne, (cle_interne, mesure, nature) in MESURES.items():
                        if colonne not in contexte:
                            continue
                        brute = contexte[colonne]
                        dax = None if brute == "" else float(brute.replace(",", "."))
                        valeur_sql = valeurs_sql[cle_interne]
                        valeur_sql = None if valeur_sql is None else float(valeur_sql)
                        if nature == "additive":
                            dax = 0.0 if dax is None else dax
                            valeur_sql = 0.0 if valeur_sql is None else valeur_sql
                        if dax is None and valeur_sql is None:
                            ecart, relatif = 0.0, 0.0
                        elif dax is None or valeur_sql is None:
                            ecart, relatif = float("inf"), float("inf")
                        else:
                            ecart = abs(dax - valeur_sql)
                            relatif = ecart / abs(valeur_sql) if valeur_sql else ecart
                        contexte_texte = f"annee={annee}" + (f", branche={branche}" if branche else "") + (
                            f", apporteur={apporteur}" if apporteur else "")
                        resultats.append({"mesure": mesure, "contexte": contexte_texte, "valeur_dax": dax,
                                          "valeur_sql": valeur_sql, "ecart_absolu": ecart, "ecart_relatif": relatif})

    sortie_csv = RACINE / "results" / "concordance_dax_sql.csv"
    with sortie_csv.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(resultats[0]))
        ecrivain.writeheader()
        ecrivain.writerows(resultats)
    ecart_max = max(r["ecart_relatif"] for r in resultats)
    hors_tolerance = [r for r in resultats if r["ecart_relatif"] > 1e-9]
    mesures = sorted({r["mesure"] for r in resultats})
    resume = {
        "comparaisons": len(resultats), "mesures": len(mesures), "contextes": len({r["contexte"] for r in resultats}),
        "ecart_relatif_maximal": ecart_max, "hors_tolerance": len(hors_tolerance),
    }
    (RACINE / "results" / "concordance_dax_sql.json").write_text(
        json.dumps({"resume": resume, "hors_tolerance": hors_tolerance[:50]}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps(resume, ensure_ascii=False))
    for r in hors_tolerance[:20]:
        print("ECART", r)
    return 0 if not hors_tolerance else 1


if __name__ == "__main__":
    raise SystemExit(main())
