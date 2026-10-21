"""Tests de l'arithmetique des montants et des taux dates.

Ce qui est verifie ici finit dans un bordereau de commissions. Un arrondi qui derive d'un centime par
ligne, sur dix mille lignes mensuelles, fait cent euros d'ecart que personne ne sait expliquer.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from courtage.domaine.montants import (
    TAUX_PLEIN_BP,
    TauxIntrouvable,
    applique_taux,
    bp_vers_pourcent,
    centimes_vers_euros,
    euros_vers_centimes,
    formate_euros,
    formate_pourcent,
    pourcent_vers_bp,
    taux_commission_applicable,
    taux_retrocession_applicable,
    taux_taxe_applicable,
)
from courtage.modeles.referentiel import Apporteur, Branche, Produit, TauxRetrocession

ESPACE = " "


# --- Application d'un taux ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("montant", "taux_bp", "attendu"),
    [
        (10_000, 1_250, 1_250),  # 100,00 EUR a 12,5 % donne 12,50 EUR
        (10_000, TAUX_PLEIN_BP, 10_000),  # taux plein : le montant est inchange
        (10_000, 0, 0),  # taux nul
        (333, 1_250, 42),  # 0,41625 EUR arrondi a 0,42 EUR
        (1, 5_000, 1),  # 0,005 centime : la demie monte, ce qui donne 1
        (3, 5_000, 2),  # 1,5 centime : la demie monte, ce qui donne 2
        (0, 1_250, 0),
    ],
)
def test_application_d_un_taux(montant: int, taux_bp: int, attendu: int) -> None:
    assert applique_taux(montant, taux_bp) == attendu


def test_la_demie_monte_toujours() -> None:
    """Choix explicite : arrondi commercial, la demie vers le haut. L'arrondi « bancaire » de Python,
    qui ramene a l'entier pair, donnerait 2 pour 2,5 et 2 pour 1,5, ce qui n'est pas la convention
    attendue sur un bordereau."""
    assert applique_taux(5, 5_000) == 3  # 2,5 monte a 3
    assert applique_taux(3, 5_000) == 2  # 1,5 monte a 2


def test_un_taux_negatif_est_refuse() -> None:
    with pytest.raises(ValueError, match="taux negatif"):
        applique_taux(1_000, -100)


def test_aucun_flottant_n_intervient() -> None:
    """Le resultat est un entier, et l'enchainement de taux ne derive pas."""
    montant = 123_456_789
    resultat = applique_taux(montant, 1_327)
    assert isinstance(resultat, int)
    assert resultat == 16_382_716


# --- Conversions et affichage -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entree", "attendu"),
    [("35,40", 3_540), ("35.40", 3_540), ("0", 0), ("1 234,56", 123_456), (68, 6_800)],
)
def test_euros_vers_centimes(entree: str | int, attendu: int) -> None:
    assert euros_vers_centimes(entree) == attendu


def test_centimes_vers_euros() -> None:
    assert centimes_vers_euros(3_540) == Decimal("35.40")


@pytest.mark.parametrize(
    ("centimes", "attendu"),
    [
        (3_540, f"35,40{ESPACE}€"),
        (0, f"0,00{ESPACE}€"),
        (123_456, f"1{ESPACE}234,56{ESPACE}€"),
        (123_456_789, f"1{ESPACE}234{ESPACE}567,89{ESPACE}€"),
        (-4_500, f"-45,00{ESPACE}€"),
    ],
)
def test_formatage_francais_des_montants(centimes: int, attendu: str) -> None:
    """Separateur de milliers en espace insecable, virgule decimale, symbole apres le nombre."""
    assert formate_euros(centimes) == attendu


def test_un_montant_negatif_s_affiche_avec_son_signe() -> None:
    """Un rejet de prelevement est un encaissement negatif : il doit se lire comme tel."""
    assert formate_euros(-4_500).startswith("-45,00")


@pytest.mark.parametrize(("pourcentage", "bp"), [("13,27", 1_327), ("12", 1_200), ("0", 0), ("100", 10_000)])
def test_conversion_pourcentage_points_de_base(pourcentage: str, bp: int) -> None:
    assert pourcent_vers_bp(pourcentage) == bp
    assert bp_vers_pourcent(bp) == Decimal(pourcentage.replace(",", "."))


def test_formatage_d_un_taux() -> None:
    assert formate_pourcent(1_327) == f"13,27{ESPACE}%"


# --- Taux dates ---------------------------------------------------------------------------------


def test_le_taux_de_taxe_est_lu_a_la_date_demandee(session) -> None:
    branche = session.scalars(select(Branche).where(Branche.code == "SI")).one()
    taux = taux_taxe_applicable(session, branche.id, date(2025, 6, 1))
    assert taux.taux_bp == 1_327


def test_un_taux_absent_a_la_date_leve_une_exception(session) -> None:
    """Appliquer zero en silence produirait un bordereau vide, decouvert des mois plus tard."""
    branche = session.scalars(select(Branche).where(Branche.code == "SI")).one()
    with pytest.raises(TauxIntrouvable):
        taux_taxe_applicable(session, branche.id, date(2015, 1, 1))


def test_le_bareme_de_commission_change_au_1er_janvier_2025(session) -> None:
    """Le referentiel genere pose deux periodes de validite. Un bordereau de 2024 relu aujourd'hui doit
    retrouver l'ancien taux, et non le taux courant."""
    produit = session.scalars(select(Produit).where(Produit.code == "SI-ESSENTIEL")).one()
    avant = taux_commission_applicable(session, produit.id, date(2024, 6, 1))
    apres = taux_commission_applicable(session, produit.id, date(2025, 6, 1))
    assert avant.date_fin_validite == date(2024, 12, 31)
    assert apres.date_debut_validite == date(2025, 1, 1)
    assert avant.taux_bp != apres.taux_bp


def test_l_assiette_de_commission_est_un_parametre_en_base(session) -> None:
    """Deux pratiques coexistent dans le metier, commissionner sur l'appele ou sur l'encaisse. Le choix
    retenu est une donnee, pas une constante du code."""
    produit = session.scalars(select(Produit).where(Produit.code == "SI-ESSENTIEL")).one()
    taux = taux_commission_applicable(session, produit.id, date(2025, 6, 1))
    assert taux.assiette.value == "cotisation_encaissee"


def test_un_accord_par_produit_prime_sur_l_accord_cadre(session) -> None:
    """Pratique du metier : on signe un cadre avec un apporteur, puis on y deroge produit par produit."""
    apporteur = session.scalars(select(Apporteur).where(Apporteur.code == "AP03")).one()
    produit_derogatoire = session.scalars(select(Produit).where(Produit.code == "PV-DECES")).one()
    produit_ordinaire = session.scalars(select(Produit).where(Produit.code == "SI-ESSENTIEL")).one()

    cadre = taux_retrocession_applicable(session, apporteur.id, produit_ordinaire.id, date(2025, 6, 1))
    derogation = taux_retrocession_applicable(session, apporteur.id, produit_derogatoire.id, date(2025, 6, 1))

    assert cadre.produit_id is None
    assert derogation.produit_id == produit_derogatoire.id
    assert derogation.taux_bp > cadre.taux_bp


def test_la_production_directe_ne_donne_lieu_a_aucune_retrocession(session) -> None:
    """Une affaire arrivee sans intermediaire n'a personne a remunerer. Le taux nul est une donnee du
    referentiel, pas un cas special dans le code."""
    apporteur = session.scalars(select(Apporteur).where(Apporteur.code == "AP09")).one()
    assert apporteur.type_apporteur.value == "direct"
    produit = session.scalars(select(Produit).where(Produit.code == "SI-ESSENTIEL")).one()
    taux = taux_retrocession_applicable(session, apporteur.id, produit.id, date(2025, 6, 1))
    assert taux.taux_bp == 0
    assert applique_taux(100_000, taux.taux_bp) == 0


def test_tous_les_taux_restent_dans_les_bornes(session) -> None:
    """Un taux de retrocession superieur a 100 % ferait reverser plus que la commission recue."""
    for taux in session.scalars(select(TauxRetrocession)):
        assert 0 <= taux.taux_bp <= TAUX_PLEIN_BP
