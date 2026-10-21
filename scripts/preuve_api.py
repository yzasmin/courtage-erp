"""Enregistre une transcription des comportements cles de l'API, contre une base deja generee.

Ce que le fichier produit sert a montrer, sans avoir a lancer le projet : la reconstitution d'un contrat
a plusieurs dates, le refus d'un acte non delegue, le refus d'une resiliation sans motif, et le format
unique des reponses d'erreur.

Il est execute contre l'application reellement demarree, par requetes HTTP, et non en appelant les
fonctions Python : ce qui est verifie est donc bien ce qu'un client verrait.

Usage : `python -m uv run python scripts/preuve_api.py --adresse http://127.0.0.1:8000`
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

from courtage.config import RACINE_PROJET


def _dates_de_reconstitution(avenants: list[dict]) -> list[str]:
    """Dates a interroger : une avant le contrat, puis une au milieu de chaque periode d'avenant.

    Deduites de l'historique plutot qu'ecrites en dur, pour que chaque avenant du contrat choisi soit
    reellement exerce, quel que soit le contrat que le script retient.
    """
    jours = [date.fromisoformat(a["date_effet"]) for a in avenants]
    dates = [jours[0] - timedelta(days=1)]
    for debut, suivant in pairwise(jours):
        dates.append(debut + (suivant - debut) // 2)
    dates.append(jours[-1] + timedelta(days=45))
    return [jour.isoformat() for jour in dates]


def _appelle(adresse: str, chemin: str, methode: str = "GET", corps: dict | None = None) -> tuple[int, dict]:
    """Appelle l'API et rend le code HTTP et le corps decode, y compris pour les refus."""
    donnees = json.dumps(corps).encode("utf-8") if corps is not None else None
    requete = urllib.request.Request(
        adresse + chemin,
        data=donnees,
        method=methode,
        headers={"Content-Type": "application/json"} if donnees else {},
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return reponse.status, json.loads(reponse.read() or b"{}")
    except urllib.error.HTTPError as erreur:
        return erreur.code, json.loads(erreur.read() or b"{}")


def _contrat_avec_historique(adresse: str) -> str:
    """Choisit un contrat qui a plusieurs avenants, pour que la reconstitution montre quelque chose."""
    _, liste = _appelle(adresse, "/api/v1/contrats?recherche=SI-2023&par_page=40")
    meilleur, meilleur_nombre = None, 0
    for ligne in liste.get("donnees", []):
        _, fiche = _appelle(adresse, f"/api/v1/contrats/{ligne['numero_contrat']}")
        nombre = len(fiche.get("avenants", []))
        if nombre > meilleur_nombre:
            meilleur, meilleur_nombre = ligne["numero_contrat"], nombre
    if meilleur is None:
        raise SystemExit("aucun contrat trouve : la base est-elle generee ?")
    return meilleur


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--adresse", default="http://127.0.0.1:8000")
    args = analyseur.parse_args()
    adresse = args.adresse.rstrip("/")

    lignes: list[str] = []

    def ecrit(texte: str = "") -> None:
        lignes.append(texte)
        print(texte)

    code, sante = _appelle(adresse, "/sante")
    if code != 200:
        print(f"l'application ne repond pas sur {adresse} (code {code})", file=sys.stderr)
        return 1

    ecrit("Transcription des comportements cles de l'API du mini-ERP de courtage.")
    ecrit(f"Adresse : {adresse}")
    ecrit(f"Enregistree le : {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    ecrit(f"Python : {platform.python_version()}")
    ecrit(f"Application : {sante.get('application')} version {sante.get('version')}")
    ecrit()

    numero = _contrat_avec_historique(adresse)
    _, fiche = _appelle(adresse, f"/api/v1/contrats/{numero}")

    ecrit("=" * 100)
    ecrit(f"1. Fiche du contrat {numero}")
    ecrit("=" * 100)
    ecrit(f"  produit          : {fiche['code_produit']}, {fiche['libelle_produit']}")
    ecrit(f"  compagnie        : {fiche['compagnie']}")
    ecrit(f"  branche          : {fiche['branche']}")
    ecrit(f"  statut courant   : {fiche['statut']}")
    ecrit(f"  cotisation       : {fiche['cotisation_mensuelle_affichee']}")
    ecrit(f"  garanties        : {len(fiche['garanties'])}")
    ecrit(f"  avenants         : {len(fiche['avenants'])}")
    ecrit()
    ecrit("  Historique des avenants :")
    for avenant in fiche["avenants"]:
        ecrit(
            f"    rang {avenant['numero_ordre']}  {avenant['date_effet']}  "
            f"{avenant['type_avenant']:26s} {avenant['statut']:10s} "
            f"formule {avenant['code_formule']}  apporteur {avenant['code_apporteur']}  "
            f"{avenant['cotisation_mensuelle_affichee']:>14s}"
        )
    ecrit()

    ecrit("=" * 100)
    ecrit("2. Etat du contrat a la date D, par reconstitution des avenants")
    ecrit("=" * 100)
    ecrit("  La reponse indique de quel avenant provient la valeur retournee.")
    ecrit()
    for jour in _dates_de_reconstitution(fiche["avenants"]):
        code, reponse = _appelle(adresse, f"/api/v1/contrats/{numero}/etat?a_la_date={jour}")
        if code == 200:
            ecrit(
                f"  {jour} -> {code}  {reponse['statut']:10s} "
                f"au portefeuille : {'oui' if reponse['est_en_portefeuille'] else 'non ':4s} "
                f"formule {reponse['code_formule']}  apporteur {reponse['code_apporteur']}  "
                f"{reponse['cotisation_mensuelle_affichee']:>14s}  "
                f"(avenant {reponse['avenant_numero_ordre']}, {reponse['avenant_type']})"
            )
        else:
            ecrit(f"  {jour} -> {code}  {reponse['erreur']['code']} : {reponse['erreur']['message']}")
    ecrit()

    ecrit("=" * 100)
    ecrit("3. Perimetre delegue par chaque compagnie, produit par produit")
    ecrit("=" * 100)
    ecrit("  Ce que l'ERP autorise depend de cette liste, et uniquement de cette liste.")
    ecrit()
    for code_produit in ("SI-ESSENTIEL", "SI-EQUILIBRE", "PV-DECES"):
        _, perimetre = _appelle(adresse, f"/api/v1/produits/{code_produit}/delegation")
        ecrit(
            f"  {code_produit:14s} convention {perimetre['convention_reference']}, "
            f"portee declaree {perimetre['portee_declaree']}"
        )
        for acte in perimetre["actes_delegues"]:
            ecrit(f"      delegue     : {acte}")
    ecrit()

    ecrit("=" * 100)
    ecrit("4. Refus metier, et format unique des reponses d'erreur")
    ecrit("=" * 100)
    ecrit()

    # Un devis reel, pour que le refus montre bien la regle du cycle de vie et non une autre.
    _, devis = _appelle(adresse, "/api/v1/contrats?statut=devis&par_page=1")
    numero_devis = devis["donnees"][0]["numero_contrat"] if devis.get("donnees") else numero

    refus = [
        (
            "resilier un devis : il n'a jamais pris effet, il n'y a rien a resilier",
            "POST",
            f"/api/v1/contrats/{numero_devis}/resiliation",
            {"date_effet": "2026-09-01", "motif": "echeance"},
        ),
        (
            "resilier sans motif : le motif est obligatoire",
            "POST",
            f"/api/v1/contrats/{numero}/resiliation",
            {"date_effet": "2026-09-01"},
        ),
        (
            "saisir un avenant anterieur au dernier avenant du contrat",
            "POST",
            f"/api/v1/contrats/{numero}/avenants",
            {"type_avenant": "revalorisation_tarifaire", "date_effet": "2020-01-01",
             "cotisation_mensuelle_cents": 7000},
        ),
        ("contrat inconnu", "GET", "/api/v1/contrats/XX-9999-99999", None),
        ("adherent inconnu", "GET", "/api/v1/adherents/A000000", None),
        ("produit inconnu", "GET", "/api/v1/produits/ZZ-INEXISTANT/delegation", None),
        (
            "etat a une date anterieure au contrat",
            "GET",
            f"/api/v1/contrats/{numero}/etat?a_la_date=2015-01-01",
            None,
        ),
        (
            "souscrire pour un adherent inconnu",
            "POST",
            "/api/v1/contrats",
            {
                "numero_adherent": "A000000",
                "code_produit": "SI-ESSENTIEL",
                "code_formule": "F1",
                "code_apporteur": "AP01",
                "date_souscription": "2026-01-15",
                "cotisation_mensuelle_cents": 5000,
            },
        ),
    ]
    for libelle, methode, chemin, corps in refus:
        code, reponse = _appelle(adresse, chemin, methode, corps)
        detail = reponse.get("erreur", {})
        ecrit(f"  {libelle}")
        ecrit(f"      {methode} {chemin}")
        ecrit(f"      -> {code}  code « {detail.get('code', '?')} »")
        ecrit(f"         {detail.get('message', reponse)}")
        ecrit()

    chemin_sortie = RACINE_PROJET / "results" / "api.txt"
    chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
    chemin_sortie.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"transcription : {chemin_sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
