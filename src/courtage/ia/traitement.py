"""Controles metier et cycle de vie d'un dossier pre-rempli (module 4a).

Le modele de langage lit ; il ne decide de rien. Ce qu'il a lu est confronte au portefeuille par des
regles ecrites ici, en Python, puis presente a un gestionnaire. Trois niveaux de controle :

- `ok` : verifie, rien a signaler ;
- `alerte` : a regarder, sans empecher la validation (un nom approchant, par exemple, que le gestionnaire
  tranche en comparant au document) ;
- `bloquant` : la validation est impossible, seul le rejet motive reste ouvert (adherent inconnu, contrat
  d'un autre adherent, soins hors garantie, total qui ne fait pas la somme de ses lignes, acte non
  delegue par la compagnie).

La validation d'une demande de remboursement ou d'une facture cree la prestation par le service qui
existe deja pour la saisie manuelle : delegation, garantie a la date des soins, couverture de la formule
et plafond annuel y sont reverifies, au moment de l'ecriture et non seulement a la lecture.
"""

from __future__ import annotations

import difflib
import json
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from courtage.domaine.avenants import EtatIntrouvable, etat_a_la_date
from courtage.domaine.delegation import ActeNonDelegue, DelegationAmbigue, verifie_acte_delegue
from courtage.ia.extraction import MODELE, ChampsExtraits, Reponse
from courtage.modeles import Adherent, Contrat, DossierPreRempli, StatutDossier
from courtage.modeles.enums import ActeGestion
from courtage.services.contrats import ReferenceInvalide
from courtage.services.prestations import (
    ContratSansGarantie,
    DemandePrestation,
    GarantieNonCouverte,
    ReferenceDejaAttribuee,
    enregistre_prestation,
    reference_suivante,
)

#: Seul un nom identique apres normalisation (accents, casse, tirets) est conforme : une lettre doublee
#: dans un nom de seize caracteres donne encore une similarite de 0,97, et un seuil a ce niveau la
#: laissait passer sans signalement. Au-dessus de ce seuil, l'ecart est signale ; en dessous, il bloque.
SEUIL_NOM_APPROCHANT = 0.80

REFUS_METIER = (
    ReferenceInvalide,
    ActeNonDelegue,
    DelegationAmbigue,
    GarantieNonCouverte,
    ContratSansGarantie,
    ReferenceDejaAttribuee,
    EtatIntrouvable,
)


@dataclass(frozen=True)
class Controle:
    code: str
    niveau: str
    message: str


class DossierNonValidable(Exception):
    """Le dossier porte un controle bloquant, n'est plus a valider, ou le service a refuse l'ecriture."""


def _normalise(texte: str) -> str:
    sans_accents = "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")
    return " ".join(sans_accents.casefold().replace("-", " ").split())


def similarite_nom(lu_prenom: str | None, lu_nom: str | None, adherent: Adherent) -> float:
    lu = _normalise(f"{lu_prenom or ''} {lu_nom or ''}")
    reference = _normalise(f"{adherent.prenom} {adherent.nom}")
    return round(difflib.SequenceMatcher(None, lu, reference).ratio(), 3)


def controle(
    session: Session, champs: ChampsExtraits
) -> tuple[list[Controle], Adherent | None, Contrat | None, float | None]:
    """Confronte les champs lus au portefeuille. Ne modifie rien."""
    resultats: list[Controle] = []
    contrat = None
    if champs.numero_contrat:
        contrat = session.scalars(select(Contrat).where(Contrat.numero_contrat == champs.numero_contrat)).first()

    # 1. L'adherent. Une attestation d'employeur ne porte pas de numero : on passe alors par le contrat.
    adherent = None
    if champs.numero_adherent:
        adherent = session.scalars(
            select(Adherent).where(Adherent.numero_adherent == champs.numero_adherent)
        ).first()
    elif contrat is not None:
        adherent = session.get(Adherent, contrat.adherent_id)
    if adherent is None:
        resultats.append(
            Controle("adherent", "bloquant", f"aucun adherent ne porte le numero {champs.numero_adherent}")
        )
    else:
        resultats.append(Controle("adherent", "ok", f"adherent {adherent.numero_adherent} trouve"))

    # 2. Le nom lu, rapproche par similarite du nom enregistre. L'ecart est affiche, jamais corrige.
    similarite = None
    if adherent is not None:
        similarite = similarite_nom(champs.prenom, champs.nom, adherent)
        lu = f"{champs.prenom or ''} {champs.nom or ''}".strip()
        ecart = f"lu « {lu} », enregistre « {adherent.prenom} {adherent.nom} » ({similarite:.2f})"
        if similarite == 1.0:
            resultats.append(Controle("nom", "ok", f"nom conforme ({similarite:.2f})"))
        elif similarite >= SEUIL_NOM_APPROCHANT:
            resultats.append(Controle("nom", "alerte", f"nom approchant : {ecart}"))
        else:
            resultats.append(Controle("nom", "bloquant", f"nom different : {ecart}"))

    # 3. Le contrat, et son rattachement a cet adherent.
    if contrat is None:
        resultats.append(Controle("contrat", "bloquant", f"aucun contrat ne porte le numero {champs.numero_contrat}"))
    elif adherent is not None and contrat.adherent_id != adherent.id:
        resultats.append(
            Controle("contrat", "bloquant", f"le contrat {contrat.numero_contrat} appartient a un autre adherent")
        )
    else:
        resultats.append(Controle("contrat", "ok", f"contrat {contrat.numero_contrat} rattache a l'adherent"))

    # 4. La garantie a la date du document, reconstituee par les avenants.
    if contrat is not None and champs.date_document is not None:
        try:
            en_garantie = etat_a_la_date(session, contrat, champs.date_document).garantie_en_cours
        except EtatIntrouvable:
            en_garantie = False
        jour = champs.date_document.strftime("%d/%m/%Y")
        # Bloquant pour un remboursement, qui engagerait un paiement sur une garantie qui ne courait pas.
        # Simple alerte pour une attestation d'employeur : elle prouve une affiliation et ne paie rien. Le
        # cas a ete trouve par l'evaluation : une attestation saine, datee pendant la suspension pour
        # impaye du contrat collectif, etait bloquee.
        niveau = "alerte" if champs.type_document == "attestation_employeur" else "bloquant"
        if en_garantie:
            resultats.append(Controle("garantie_a_date", "ok", f"contrat en garantie le {jour}"))
        else:
            message = f"contrat sans garantie en cours le {jour} (suspendu ou pas en vigueur)"
            resultats.append(Controle("garantie_a_date", niveau, message))
    elif champs.date_document is None:
        resultats.append(Controle("garantie_a_date", "bloquant", "aucune date lue sur le document"))

    if champs.type_document == "attestation_employeur":
        return resultats, adherent, contrat, similarite

    # 5. Les montants : un total present, positif, egal a la somme des lignes.
    total = champs.montant_total_cents
    somme = sum(ligne.montant_cents for ligne in champs.lignes)
    if total is None or total <= 0:
        resultats.append(Controle("montants", "bloquant", "aucun total positif lu sur le document"))
    elif champs.lignes and somme != total:
        resultats.append(
            Controle(
                "montants",
                "bloquant",
                f"le total ecrit ({total / 100:.2f} EUR) ne fait pas la somme des lignes ({somme / 100:.2f} EUR)",
            )
        )
    else:
        resultats.append(Controle("montants", "ok", f"total de {total / 100:.2f} EUR coherent avec les lignes"))
    if champs.code_garantie is None:
        resultats.append(Controle("garantie_invoquee", "bloquant", "aucune garantie identifiee"))

    # 6. La delegation de la gestion des prestations, a la date des soins.
    if contrat is not None and champs.date_document is not None:
        try:
            verifie_acte_delegue(session, contrat.produit_id, ActeGestion.GESTION_PRESTATIONS, champs.date_document)
            resultats.append(Controle("delegation", "ok", "gestion des prestations deleguee au cabinet"))
        except (ActeNonDelegue, DelegationAmbigue) as refus:
            resultats.append(Controle("delegation", "bloquant", str(refus)))
    return resultats, adherent, contrat, similarite


def cree_dossier(session: Session, nom_fichier: str, reponse: Reponse) -> DossierPreRempli:
    """Depose le dossier au statut `a_valider`. Aucune autre ecriture."""
    controles, adherent, contrat, similarite = controle(session, reponse.champs)
    dossier = DossierPreRempli(
        nom_fichier=nom_fichier,
        type_document=reponse.champs.type_document,
        statut=StatutDossier.A_VALIDER,
        adherent_id=adherent.id if adherent else None,
        contrat_id=contrat.id if contrat else None,
        extraction=reponse.champs.model_dump_json(),
        controles=json.dumps([asdict(c) for c in controles], ensure_ascii=False),
        similarite_nom=similarite,
        montant_total_cents=reponse.champs.montant_total_cents,
        modele=reponse.modele,
        jetons_entree=reponse.jetons_entree,
        jetons_sortie=reponse.jetons_sortie,
        cout_microdollars=reponse.cout_microdollars,
        latence_ms=reponse.latence_ms,
    )
    session.add(dossier)
    session.flush()
    return dossier


def cree_dossier_en_echec(session: Session, nom_fichier: str, motif: str) -> DossierPreRempli:
    """Un document que l'agent n'a pas su lire reste visible du gestionnaire, avec la raison."""
    dossier = DossierPreRempli(
        nom_fichier=nom_fichier,
        type_document=None,
        statut=StatutDossier.A_VALIDER,
        extraction="{}",
        controles=json.dumps([asdict(Controle("extraction", "bloquant", motif))], ensure_ascii=False),
        modele=MODELE,
        jetons_entree=0,
        jetons_sortie=0,
        cout_microdollars=0,
        latence_ms=0,
    )
    session.add(dossier)
    session.flush()
    return dossier


def controles_du_dossier(dossier: DossierPreRempli) -> list[Controle]:
    return [Controle(**c) for c in json.loads(dossier.controles)]


def valide_dossier(session: Session, dossier: DossierPreRempli) -> None:
    """Decision humaine de validation : la seule voie vers une ecriture definitive."""
    if dossier.statut is not StatutDossier.A_VALIDER:
        raise DossierNonValidable(f"le dossier est deja {dossier.statut.value}")
    bloquants = [c for c in controles_du_dossier(dossier) if c.niveau == "bloquant"]
    if bloquants:
        raise DossierNonValidable(f"controle bloquant : {bloquants[0].message}")
    champs = ChampsExtraits.model_validate_json(dossier.extraction)
    if champs.type_document != "attestation_employeur":
        demande = DemandePrestation(
            numero_contrat=champs.numero_contrat,
            code_garantie=champs.code_garantie,
            date_soins=champs.date_document,
            montant_demande_cents=champs.montant_total_cents,
        )
        try:
            resultat = enregistre_prestation(session, demande, reference_suivante(session, champs.date_document))
        except REFUS_METIER as refus:
            raise DossierNonValidable(str(refus)) from refus
        dossier.prestation_id = resultat.prestation.id
    dossier.statut = StatutDossier.VALIDE
    dossier.decide_le = datetime.now()
    session.flush()


def rejette_dossier(session: Session, dossier: DossierPreRempli, motif: str) -> None:
    if dossier.statut is not StatutDossier.A_VALIDER:
        raise DossierNonValidable(f"le dossier est deja {dossier.statut.value}")
    if not motif.strip():
        raise DossierNonValidable("un rejet doit etre motive")
    dossier.statut = StatutDossier.REJETE
    dossier.motif_rejet = motif.strip()[:300]
    dossier.decide_le = datetime.now()
    session.flush()
