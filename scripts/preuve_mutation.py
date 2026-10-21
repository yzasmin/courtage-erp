"""Verifie que les tests detectent bien les defauts qu'ils pretendent couvrir.

Un test qui passe ne prouve rien tant qu'on n'a pas vu qu'il pouvait echouer. Ce script reintroduit
volontairement un defaut dans le code, relance les tests concernes, et exige qu'ils echouent. Il remet
ensuite le code en etat et verifie qu'ils repassent.

Chaque mutation ci-dessous correspond a un trou reel, signale par une verification independante : le
controle existait dans le code mais aucun test ne tombait quand on le supprimait.

Le script restaure toujours les fichiers, y compris en cas d'interruption. Il travaille sur une copie
de sauvegarde prise au demarrage, jamais sur un depot modifie.

Usage : `python -m uv run python scripts/preuve_mutation.py`
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from courtage.config import RACINE_PROJET


@dataclass(frozen=True, slots=True)
class Mutation:
    """Un defaut a reintroduire, et les tests qui doivent le detecter."""

    code: str
    description: str
    fichier: str
    avant: str
    apres: str
    tests: tuple[str, ...]


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        code="compteur_de_reference_global",
        description=(
            "Reprendre le compteur de reference de prestation sur toutes les periodes au lieu du"
            " seul mois des soins"
        ),
        fichier="src/courtage/services/prestations.py",
        avant="""        select(func.max(Prestation.reference_prestation)).where(
            Prestation.reference_prestation.like(f"{prefixe}%")
        )""",
        apres="        select(func.max(Prestation.reference_prestation))",
        tests=(
            "tests/test_prestations.py::test_deux_saisies_sur_un_mois_anterieur_ne_collisionnent_pas",
        ),
    ),
    Mutation(
        code="ecran_anomalies_exclut_les_appels_groupes",
        description=(
            "Revenir a la jointure interne sur contrat_id dans l'ecran des anomalies, ce qui exclut"
            " les ecarts portant sur un appel groupe"
        ),
        fichier="src/courtage/interface/vues.py",
        avant="    return requete.outerjoin(Contrat, Contrat.id == AppelCotisation.contrat_id).outerjoin(",
        apres="    return requete.join(Contrat, Contrat.id == AppelCotisation.contrat_id).outerjoin(",
        tests=(
            "tests/test_api.py::test_l_ecran_des_anomalies_montre_le_rapprochement_et_les_lots_rejetes",
        ),
    ),
    Mutation(
        code="borne_de_resiliation_relachee",
        description=(
            "Relacher la borne du controle de periode : accepter une periode qui commence le jour"
            " meme de la resiliation"
        ),
        fichier="src/courtage/flux/controles.py",
        avant="if contexte.date_resiliation is not None and debut >= contexte.date_resiliation:",
        apres="if contexte.date_resiliation is not None and debut > contexte.date_resiliation:",
        tests=(
            "tests/flux/test_controles_bloquants.py::test_periode_commencant_le_jour_de_la_resiliation_rejette_le_lot",
        ),
    ),
    Mutation(
        code="type_avenant_non_controle",
        description="Ne plus verifier que le type d'avenant correspond a la transition demandee",
        fichier="src/courtage/domaine/cycle_vie.py",
        avant="""    type_attendu = TYPE_ATTENDU_PAR_TRANSITION[(depart, arrivee)]
    if type_avenant is not type_attendu:""",
        apres="""    type_attendu = TYPE_ATTENDU_PAR_TRANSITION[(depart, arrivee)]
    if False:""",
        tests=(
            "tests/test_cycle_vie.py::test_le_type_d_avenant_est_refuse_a_travers_le_service",
            "tests/test_cycle_vie.py::test_une_suspension_etiquetee_remise_en_vigueur_est_refusee",
        ),
    ),
    Mutation(
        code="cotisation_non_reportee",
        description="Ne plus reporter la cotisation de l'avenant sur le contrat",
        fichier="src/courtage/domaine/avenants.py",
        avant="    contrat.cotisation_mensuelle_cents = avenant.cotisation_mensuelle_cents\n",
        apres="",
        tests=(
            "tests/test_avenants.py::test_le_contrat_reprend_la_cotisation_de_son_dernier_avenant",
            "tests/test_avenants.py::test_le_cache_du_contrat_egale_la_reconstitution",
        ),
    ),
    Mutation(
        code="debut_validite_ignore",
        description="Ignorer la date de debut de validite d'une convention de delegation",
        fichier="src/courtage/domaine/delegation.py",
        avant="            ConventionDelegation.date_debut_validite <= a_la_date,",
        apres="",
        tests=(
            "tests/test_delegation.py::test_une_convention_pas_encore_en_vigueur_n_autorise_rien",
        ),
    ),
    Mutation(
        code="plafond_non_cumule",
        description="Appliquer le plafond annuel a chaque prestation au lieu de le cumuler",
        fichier="src/courtage/services/prestations.py",
        avant="        reste = max(0, couverture.plafond_annuel_cents - deja)",
        apres="        reste = couverture.plafond_annuel_cents",
        tests=("tests/test_prestations.py::test_le_plafond_annuel_se_consomme_sur_l_annee",),
    ),
    Mutation(
        code="garantie_suspendue_ignoree",
        description="Servir une prestation sur un contrat dont la garantie est suspendue",
        fichier="src/courtage/services/prestations.py",
        avant="    if not etat.garantie_en_cours:",
        apres="    if not etat.est_en_portefeuille:",
        tests=("tests/test_prestations.py::test_un_contrat_suspendu_n_ouvre_droit_a_rien",),
    ),
    Mutation(
        code="delegation_prestation_ignoree",
        description="Ne plus verifier la delegation avant d'enregistrer une prestation",
        fichier="src/courtage/services/prestations.py",
        avant="""    verifie_acte_delegue(
        session, contrat.produit_id, ActeGestion.GESTION_PRESTATIONS, demande.date_soins
    )""",
        apres="    pass",
        tests=(
            "tests/test_prestations.py::test_une_prestation_est_refusee_quand_la_gestion_n_est_pas_deleguee",
            "tests/test_prestations.py::test_le_refus_de_prestation_repond_409",
        ),
    ),
)


def _lit(chemin) -> tuple[str, str]:
    """Lit un fichier et rend son texte en fins de ligne normalisees, plus la convention d'origine.

    Deux exigences a concilier. Les motifs de mutation sont ecrits avec des retours simples, donc la
    recherche doit se faire sur un texte normalise. Et le fichier restaure doit etre identique a
    l'octet pres, sinon git y voit une modification et le garde-fou de ce script se declenche sur sa
    propre trace. D'ou la normalisation pour chercher, et la restitution a l'identique pour ecrire.

    `Path.read_text` n'accepte le parametre `newline` qu'a partir de Python 3.13, d'ou `open`.
    """
    with open(chemin, encoding="utf-8", newline="") as fichier:
        brut = fichier.read()
    fin_de_ligne = "\r\n" if "\r\n" in brut else "\n"
    return brut.replace("\r\n", "\n"), fin_de_ligne


def _ecrit(chemin, contenu: str, fin_de_ligne: str) -> None:
    """Ecrit un fichier en lui rendant sa convention de fin de ligne d'origine."""
    with open(chemin, "w", encoding="utf-8", newline="") as fichier:
        fichier.write(contenu.replace("\n", fin_de_ligne))


def _lance(tests: tuple[str, ...]) -> bool:
    """Lance les tests donnes. Rend True si tout passe."""
    resultat = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", *tests],
        cwd=str(RACINE_PROJET),
        capture_output=True,
        text=True,
        check=False,
    )
    return resultat.returncode == 0


def main() -> int:
    originaux: dict[str, str] = {}
    fins_de_ligne: dict[str, str] = {}
    for mutation in MUTATIONS:
        chemin = RACINE_PROJET / mutation.fichier
        if mutation.fichier not in originaux:
            originaux[mutation.fichier], fins_de_ligne[mutation.fichier] = _lit(chemin)

    resultats: list[dict] = []
    echecs = 0

    try:
        for mutation in MUTATIONS:
            chemin = RACINE_PROJET / mutation.fichier
            source = originaux[mutation.fichier]
            if mutation.avant not in source:
                print(f"  IGNORE {mutation.code} : le code a change, la mutation ne s'applique plus")
                resultats.append({"code": mutation.code, "applicable": False, "detecte": False})
                echecs += 1
                continue

            _ecrit(
                chemin,
                source.replace(mutation.avant, mutation.apres, 1),
                fins_de_ligne[mutation.fichier],
            )
            detecte = not _lance(mutation.tests)
            _ecrit(chemin, source, fins_de_ligne[mutation.fichier])

            marque = "ok    " if detecte else "ECHEC "
            if not detecte:
                echecs += 1
            print(f"  {marque} {mutation.description}")
            print(f"           defaut {'detecte' if detecte else 'NON detecte'} par {len(mutation.tests)} test(s)")
            resultats.append(
                {
                    "code": mutation.code,
                    "description": mutation.description,
                    "fichier": mutation.fichier,
                    "tests": list(mutation.tests),
                    "applicable": True,
                    "detecte": detecte,
                }
            )
    finally:
        # Restauration systematique, meme en cas d'interruption.
        for fichier, source in originaux.items():
            _ecrit(RACINE_PROJET / fichier, source, fins_de_ligne[fichier])

    # Le code est remis en etat : la suite doit repasser.
    tous_les_tests = tuple(sorted({t for m in MUTATIONS for t in m.tests}))
    remise_en_etat = _lance(tous_les_tests)
    if not remise_en_etat:
        echecs += 1

    rapport = {
        "mesure_le": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mutations": len(MUTATIONS),
        "detectees": sum(1 for r in resultats if r.get("detecte")),
        "code_remis_en_etat": remise_en_etat,
        "conforme": echecs == 0,
        "detail": resultats,
    }
    dossier = RACINE_PROJET / "results"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin_rapport = dossier / "mutation.json"
    chemin_rapport.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"  code remis en etat, tests de nouveau verts : {'oui' if remise_en_etat else 'NON'}")
    if echecs == 0:
        print(f"CONFORME : les {len(MUTATIONS)} defauts reintroduits sont tous detectes")
    else:
        print(f"NON CONFORME : {echecs} mutation(s) non detectee(s)", file=sys.stderr)
    print(f"rapport : {chemin_rapport}")
    return 0 if echecs == 0 else 1


def _verifie_depot_propre() -> None:
    """Refuse de tourner sur un depot dont les fichiers mutes sont deja modifies."""
    fichiers = sorted({m.fichier for m in MUTATIONS})
    resultat = subprocess.run(
        ["git", "status", "--porcelain", "--", *fichiers],
        cwd=str(RACINE_PROJET),
        capture_output=True,
        text=True,
        check=False,
    )
    if resultat.stdout.strip():
        print(
            "Les fichiers a muter ont des modifications non validees :\n"
            f"{resultat.stdout}"
            "Validez-les d'abord, pour qu'une interruption ne puisse rien perdre.",
            file=sys.stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _verifie_depot_propre()
    raise SystemExit(main())


