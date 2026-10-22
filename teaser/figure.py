"""Trace la figure du teaser : ratio sinistres sur primes par exercice et par branche.

Lit results/powerbi/01_par_annee.csv et 02_par_annee_branche.csv (valeurs des mesures DAX, concordantes avec le
SQL de controle, voir results/concordance_dax_sql.csv). Aucune valeur n'est saisie a la main.
Usage : python teaser/figure.py   (ecrit teaser/figure.png, 1600 x 900)
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RACINE = Path(__file__).resolve().parents[1]
FOND, TEXTE, ACCENT, SECONDAIRE = "#0D0F12", "#ECE8DF", "#F2B84B", "#5BC0A8"


def lire(nom):
    with open(RACINE / "results" / "powerbi" / nom, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def nombre(texte):
    return float(texte.replace(",", ".")) if texte else None


global_ = {r["dim_date[annee]"]: nombre(r["[Ratio SP]"]) * 100 for r in lire("01_par_annee.csv")}
branche = {(r["dim_date[annee]"], r["dim_branche[code_branche]"]): nombre(r["[Ratio SP]"]) for r in lire("02_par_annee_branche.csv")}
annees = ["2024", "2025", "2026"]
etiquettes = ["2024", "2025", "2026 (9 mois)"]
series = [("SI", "Santé individuelle", SECONDAIRE), ("SC", "Santé collective", ACCENT)]

fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor=FOND)
ax.set_facecolor(FOND)
largeur = 0.32
for k, (code, libelle, couleur) in enumerate(series):
    xs = [i + (k - 0.5) * largeur for i in range(len(annees))]
    vals = [branche[(a, code)] * 100 for a in annees]
    barres = ax.bar(xs, vals, width=largeur * 0.92, color=couleur, label=libelle)
    for x, v in zip(xs, vals):
        ax.text(x, v + 1.2, f"{v:.1f} %".replace(".", ","), ha="center", color=TEXTE, fontsize=15)
for i, a in enumerate(annees):
    ax.text(i, 93, f"Ensemble : {global_[a]:.2f} %".replace(".", ","), ha="center", color=FOND, fontsize=16,
            fontweight="bold", bbox=dict(boxstyle="round,pad=0.4", fc=TEXTE, ec="none"))
ax.set_xticks(range(len(annees)), etiquettes, color=TEXTE, fontsize=17)
ax.tick_params(axis="x", pad=8)
ax.set_ylim(0, 102)
ax.set_ylabel("Prestations réglées sur cotisations acquises (%)", color=TEXTE, fontsize=14)
ax.tick_params(colors=TEXTE, labelsize=14)
ax.grid(axis="y", color="#ECE8DF", alpha=0.08)
for c in ("top", "right"):
    ax.spines[c].set_visible(False)
for c in ("left", "bottom"):
    ax.spines[c].set_color("#3A3D44")
ax.set_title("Ratio sinistres sur primes, par exercice et par branche (jeu simulé)", color=TEXTE, fontsize=20, pad=22)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2, frameon=False, labelcolor=TEXTE, fontsize=15)
fig.tight_layout()
fig.savefig(RACINE / "teaser" / "figure.png", facecolor=FOND)
