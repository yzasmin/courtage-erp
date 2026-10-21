"""Tests de l'API : codes de retour, endpoint d'etat a la date, et traduction des refus metier.

Ce qui est verifie ici n'est pas seulement que l'API repond, mais qu'elle repond **le bon code**. Un
client qui recoit 400 corrige sa requete ; un client qui recoit 409 va voir l'etat du systeme. Se
tromper de code envoie le lecteur dans la mauvaise direction.
"""

from __future__ import annotations

from datetime import date

import pytest

from courtage.modeles.enums import MotifResiliation, StatutContrat
from courtage.services import contrats as service

DATE_SOUSCRIPTION = date(2024, 2, 10)
DATE_EFFET = date(2024, 3, 1)


# --- Exploitation et documentation ---------------------------------------------------------------


def test_l_etat_de_service_repond(client) -> None:
    reponse = client.get("/sante")
    assert reponse.status_code == 200
    assert reponse.json()["etat"] == "ok"


def test_la_documentation_openapi_est_produite_par_le_code(client) -> None:
    """La documentation n'est pas ecrite a la main : elle vient des schemas, donc elle ne peut pas
    decrire une API qui n'existe pas."""
    reponse = client.get("/api/openapi.json")
    assert reponse.status_code == 200
    schema = reponse.json()
    chemins = schema["paths"]
    assert "/api/v1/contrats/{numero_contrat}/etat" in chemins
    assert "/api/v1/contrats" in chemins
    assert "/api/v1/adherents" in chemins
    assert "/api/v1/apporteurs" in chemins
    assert "/api/v1/produits/{code_produit}/delegation" in chemins
    # Chaque operation porte un resume lisible.
    for chemin, operations in chemins.items():
        for methode, operation in operations.items():
            assert operation.get("summary"), f"{methode.upper()} {chemin} n'a pas de resume"


def test_la_page_de_documentation_s_affiche(client) -> None:
    assert client.get("/api/doc").status_code == 200


# --- Lecture --------------------------------------------------------------------------------------


def test_liste_des_adherents_paginee(client, adherent) -> None:
    reponse = client.get("/api/v1/adherents", params={"par_page": 5})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["pagination"]["par_page"] == 5
    assert len(corps["donnees"]) <= 5
    assert corps["pagination"]["total"] >= 1
    # L'adherent du test est retrouve par la recherche, et non suppose present sur la premiere page :
    # la suite doit aussi passer contre la base de demonstration et ses milliers d'adherents.
    cible = client.get("/api/v1/adherents", params={"recherche": adherent.numero_adherent})
    assert any(
        ligne["numero_adherent"] == adherent.numero_adherent for ligne in cible.json()["donnees"]
    )


def test_recherche_d_un_adherent_par_nom(client, adherent) -> None:
    reponse = client.get("/api/v1/adherents", params={"recherche": "teissier"})
    assert reponse.status_code == 200
    assert reponse.json()["pagination"]["total"] >= 1


def test_fiche_d_un_adherent_inconnu_repond_404(client) -> None:
    reponse = client.get("/api/v1/adherents/A000000")
    assert reponse.status_code == 404


def test_fiche_d_un_contrat_inconnu_repond_404(client) -> None:
    reponse = client.get("/api/v1/contrats/XX-9999-99999")
    assert reponse.status_code == 404
    assert reponse.json()["erreur"]["code"] == "contrat_introuvable"


def test_la_fiche_contrat_porte_garanties_avenants_et_delegation(client, session, contrat_oceane) -> None:
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    reponse = client.get(f"/api/v1/contrats/{contrat_oceane.numero_contrat}")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["garanties"], "la fiche doit porter le tableau de garanties de la formule"
    assert len(corps["avenants"]) == 2
    assert corps["perimetre_delegue"]["convention_reference"] == "CONV-OCE-2020"
    assert corps["cotisation_mensuelle_affichee"].endswith("€")


# --- Endpoint « etat du contrat a la date D » ----------------------------------------------------


def test_etat_a_une_date_anterieure_a_la_souscription_repond_404(client, contrat_oceane) -> None:
    reponse = client.get(
        f"/api/v1/contrats/{contrat_oceane.numero_contrat}/etat", params={"a_la_date": "2020-01-01"}
    )
    assert reponse.status_code == 404
    assert reponse.json()["erreur"]["code"] == "etat_introuvable"


def test_etat_a_une_date_donnee(client, session, contrat_oceane) -> None:
    from courtage.modeles.enums import TypeAvenant

    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    service.ajoute_avenant(
        session,
        contrat_oceane,
        type_avenant=TypeAvenant.REVALORISATION_TARIFAIRE,
        date_effet=date(2025, 1, 1),
        cotisation_mensuelle_cents=7_250,
    )

    avant = client.get(
        f"/api/v1/contrats/{contrat_oceane.numero_contrat}/etat", params={"a_la_date": "2024-09-01"}
    ).json()
    apres = client.get(
        f"/api/v1/contrats/{contrat_oceane.numero_contrat}/etat", params={"a_la_date": "2025-09-01"}
    ).json()

    assert avant["cotisation_mensuelle_cents"] == 6_840
    assert apres["cotisation_mensuelle_cents"] == 7_250
    # La reponse dit de quel acte provient la valeur : sans cela, une valeur contestee est indefendable.
    assert avant["avenant_type"] == "mise_en_vigueur"
    assert apres["avenant_type"] == "revalorisation_tarifaire"
    assert apres["avenant_date_effet"] == "2025-01-01"


def test_etat_sans_date_utilise_aujourd_hui(client, session, contrat_oceane) -> None:
    service.met_en_vigueur(session, contrat_oceane, DATE_EFFET)
    reponse = client.get(f"/api/v1/contrats/{contrat_oceane.numero_contrat}/etat")
    assert reponse.status_code == 200
    assert reponse.json()["a_la_date"] == date.today().isoformat()


def test_etat_d_un_devis_indique_qu_il_n_est_pas_au_portefeuille(client, contrat_oceane) -> None:
    reponse = client.get(
        f"/api/v1/contrats/{contrat_oceane.numero_contrat}/etat",
        params={"a_la_date": DATE_SOUSCRIPTION.isoformat()},
    )
    corps = reponse.json()
    assert corps["statut"] == StatutContrat.DEVIS.value
    assert corps["est_en_portefeuille"] is False


# --- Ecriture --------------------------------------------------------------------------------------


def test_souscription_cree_un_devis(client, adherent) -> None:
    reponse = client.post(
        "/api/v1/contrats",
        json={
            "numero_adherent": adherent.numero_adherent,
            "code_produit": "SI-ESSENTIEL",
            "code_formule": "F2",
            "code_apporteur": "AP01",
            "date_souscription": DATE_SOUSCRIPTION.isoformat(),
            "cotisation_mensuelle_cents": 6_840,
            "fractionnement": "mensuel",
        },
    )
    assert reponse.status_code == 201
    assert "Location" in reponse.headers
    corps = reponse.json()
    assert corps["statut"] == StatutContrat.DEVIS.value
    assert corps["date_effet"] is None


def test_souscription_avec_un_adherent_inconnu_repond_422(client) -> None:
    reponse = client.post(
        "/api/v1/contrats",
        json={
            "numero_adherent": "A000000",
            "code_produit": "SI-ESSENTIEL",
            "code_formule": "F2",
            "code_apporteur": "AP01",
            "date_souscription": DATE_SOUSCRIPTION.isoformat(),
            "cotisation_mensuelle_cents": 6_840,
        },
    )
    assert reponse.status_code == 422
    assert reponse.json()["erreur"]["code"] == "reference_invalide"


def test_souscription_avec_une_cotisation_negative_est_refusee(client, adherent) -> None:
    """Refus par le schema Pydantic, avant meme d'atteindre le service."""
    reponse = client.post(
        "/api/v1/contrats",
        json={
            "numero_adherent": adherent.numero_adherent,
            "code_produit": "SI-ESSENTIEL",
            "code_formule": "F2",
            "code_apporteur": "AP01",
            "date_souscription": DATE_SOUSCRIPTION.isoformat(),
            "cotisation_mensuelle_cents": -1,
        },
    )
    assert reponse.status_code in (422, 400)


def test_mise_en_vigueur_puis_resiliation(client, contrat_oceane) -> None:
    numero = contrat_oceane.numero_contrat
    reponse = client.post(
        f"/api/v1/contrats/{numero}/mise-en-vigueur", json={"date_effet": DATE_EFFET.isoformat()}
    )
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == StatutContrat.EN_COURS.value

    reponse = client.post(
        f"/api/v1/contrats/{numero}/resiliation",
        json={"date_effet": "2026-01-01", "motif": MotifResiliation.ECHEANCE.value},
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == StatutContrat.RESILIE.value
    assert corps["motif_resiliation"] == MotifResiliation.ECHEANCE.value


def test_resiliation_sans_motif_est_refusee_par_le_schema(client, contrat_oceane) -> None:
    """Le motif n'est pas optionnel dans le schema : la demande est rejetee avant toute ecriture."""
    reponse = client.post(
        f"/api/v1/contrats/{contrat_oceane.numero_contrat}/resiliation",
        json={"date_effet": "2026-01-01"},
    )
    assert reponse.status_code == 422


def test_resiliation_avec_un_motif_inconnu_est_refusee(client, contrat_oceane) -> None:
    reponse = client.post(
        f"/api/v1/contrats/{contrat_oceane.numero_contrat}/resiliation",
        json={"date_effet": "2026-01-01", "motif": "parce_que"},
    )
    assert reponse.status_code == 422


def test_resilier_un_devis_repond_409(client, contrat_oceane) -> None:
    """La demande est bien formee ; c'est l'etat du contrat qui s'y oppose, donc un conflit."""
    reponse = client.post(
        f"/api/v1/contrats/{contrat_oceane.numero_contrat}/resiliation",
        json={"date_effet": "2024-04-01", "motif": MotifResiliation.ECHEANCE.value},
    )
    assert reponse.status_code == 409
    assert reponse.json()["erreur"]["code"] == "transition_interdite"


def test_un_contrat_resilie_refuse_un_avenant_avec_409(client, contrat_oceane) -> None:
    numero = contrat_oceane.numero_contrat
    client.post(f"/api/v1/contrats/{numero}/mise-en-vigueur", json={"date_effet": DATE_EFFET.isoformat()})
    client.post(
        f"/api/v1/contrats/{numero}/resiliation",
        json={"date_effet": "2025-06-01", "motif": MotifResiliation.NON_PAIEMENT.value},
    )
    reponse = client.post(
        f"/api/v1/contrats/{numero}/avenants",
        json={"type_avenant": "remise_en_vigueur", "date_effet": "2025-07-01"},
    )
    assert reponse.status_code == 409
    assert reponse.json()["erreur"]["code"] == "contrat_resilie"


def test_un_avenant_anterieur_au_precedent_repond_409(client, contrat_oceane) -> None:
    numero = contrat_oceane.numero_contrat
    client.post(f"/api/v1/contrats/{numero}/mise-en-vigueur", json={"date_effet": DATE_EFFET.isoformat()})
    reponse = client.post(
        f"/api/v1/contrats/{numero}/avenants",
        json={
            "type_avenant": "revalorisation_tarifaire",
            "date_effet": "2023-01-01",
            "cotisation_mensuelle_cents": 7_000,
        },
    )
    assert reponse.status_code == 409
    assert reponse.json()["erreur"]["code"] == "date_avenant_incoherente"


def test_un_avenant_change_bien_la_cotisation(client, contrat_oceane) -> None:
    numero = contrat_oceane.numero_contrat
    client.post(f"/api/v1/contrats/{numero}/mise-en-vigueur", json={"date_effet": DATE_EFFET.isoformat()})
    reponse = client.post(
        f"/api/v1/contrats/{numero}/avenants",
        json={
            "type_avenant": "revalorisation_tarifaire",
            "date_effet": "2025-01-01",
            "cotisation_mensuelle_cents": 7_250,
            "commentaire": "Revalorisation a l'echeance",
        },
    )
    assert reponse.status_code == 201
    assert reponse.json()["cotisation_mensuelle_cents"] == 7_250


# --- Delegation vue de l'API ---------------------------------------------------------------------


def test_le_perimetre_delegue_est_expose(client) -> None:
    reponse = client.get("/api/v1/produits/PV-DECES/delegation")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["convention_reference"] == "CONV-LIT-2020"
    assert not any("prestation" in acte for acte in corps["actes_delegues"])


def test_un_produit_inconnu_repond_404(client) -> None:
    assert client.get("/api/v1/produits/ZZ-INEXISTANT/delegation").status_code == 404


def test_une_souscription_non_deleguee_repond_409(client, session, adherent) -> None:
    from courtage.modeles.delegation import ActeDelegue
    from courtage.modeles.enums import ActeGestion

    session.execute(ActeDelegue.__table__.delete().where(ActeDelegue.acte == ActeGestion.AFFILIATION))
    session.flush()

    reponse = client.post(
        "/api/v1/contrats",
        json={
            "numero_adherent": adherent.numero_adherent,
            "code_produit": "SI-ESSENTIEL",
            "code_formule": "F2",
            "code_apporteur": "AP01",
            "date_souscription": DATE_SOUSCRIPTION.isoformat(),
            "cotisation_mensuelle_cents": 6_840,
        },
    )
    assert reponse.status_code == 409
    assert reponse.json()["erreur"]["code"] == "acte_non_delegue"
    # Le message dit ce qui est reellement delegue, pour que le gestionnaire sache quoi faire.
    assert "convention" in reponse.json()["erreur"]["message"].lower()


# --- Reseau ---------------------------------------------------------------------------------------


def test_la_liste_des_apporteurs_porte_la_production(client) -> None:
    reponse = client.get("/api/v1/apporteurs")
    assert reponse.status_code == 200
    donnees = reponse.json()["donnees"]
    assert len(donnees) == 10
    directs = [a for a in donnees if a["type_apporteur"] == "direct"]
    assert directs, "le reseau simule comprend des canaux de production directe"
    assert all(a["taux_retrocession_cadre"].startswith("0,00") for a in directs), (
        "la production directe n'a pas d'intermediaire a remunerer, donc pas de retrocession"
    )


def test_un_apporteur_inconnu_repond_404(client) -> None:
    assert client.get("/api/v1/apporteurs/AP99").status_code == 404


ECRANS = ("/", "/adherents", "/contrats", "/contrats/nouveau", "/anomalies", "/dossiers-a-valider", "/reseau")


@pytest.mark.parametrize("chemin", ECRANS)
def test_les_ecrans_de_l_interface_repondent(client, chemin: str) -> None:
    reponse = client.get(chemin)
    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("text/html")


def test_l_ecran_des_anomalies_montre_le_rapprochement_et_les_lots_rejetes(
    client, session, contrat_oceane
) -> None:
    """L'ecran des anomalies lit la chaine des flux, et non les impayes du module 1.

    Ce test couvre les deux defauts corriges en meme temps.

    D'abord la source : l'ecran lisait `appel_cotisation.statut = 'impaye'`, un etat du
    quittancement, alors que la specification demande que les ecarts du **rapprochement**
    l'alimentent, et que l'exposure dbt `ecran_anomalies_erp` annonce les lots rejetes et les ecarts.
    Il lit maintenant `lot_fichier`, `anomalie_lot` et `rapprochement_ligne`.

    Ensuite la jointure : les requetes joignaient `contrat` sur `appel_cotisation.contrat_id` en
    jointure interne. Un appel groupe adresse a une entreprise souscriptrice porte `police_id` et
    laisse `contrat_id` nul : il etait donc exclu, et avec lui les ecarts des polices collectives,
    c'est-a-dire les plus gros montants du portefeuille. L'ecart construit ici porte sur une police,
    et le test exige de lire son numero a l'ecran.
    """
    from datetime import datetime

    from sqlalchemy import select

    from courtage.flux.enums import (
        CodeAnomalie,
        FormatFichier,
        MethodeRapprochement,
        SeveriteAnomalie,
        StatutLot,
        TypeFlux,
    )
    from courtage.flux.modeles import AnomalieLot, LotFichier, RapprochementLigne
    from courtage.modeles.collectif import PoliceCollective
    from courtage.modeles.enums import StatutAppel, StatutContrat
    from courtage.modeles.financier import AppelCotisation
    from courtage.modeles.portefeuille import EntrepriseSouscriptrice

    entreprise = session.scalars(select(EntrepriseSouscriptrice).limit(1)).first()
    if entreprise is None:
        entreprise = EntrepriseSouscriptrice(
            siren="123456789",
            raison_sociale="Entreprise de test",
            code_naf="62.01Z",
            effectif=12,
            departement="34",
            date_adhesion=date(2025, 12, 1),
        )
        session.add(entreprise)
        session.flush()
    police = PoliceCollective(
        numero_police="PC-TEST-00001",
        entreprise_id=entreprise.id,
        produit_id=contrat_oceane.produit_id,
        formule_socle_id=contrat_oceane.formule_id,
        apporteur_id=contrat_oceane.apporteur_id,
        statut=StatutContrat.EN_COURS,
        date_souscription=date(2025, 12, 1),
        date_effet=date(2026, 1, 1),
        fractionnement=contrat_oceane.fractionnement,
    )
    session.add(police)
    session.flush()

    appel_groupe = AppelCotisation(
        reference_appel="APP-POLICE-202606",
        contrat_id=None,
        police_id=police.id,
        nombre_affilies=12,
        periode_debut=date(2026, 6, 1),
        periode_fin=date(2026, 6, 30),
        date_echeance=date(2026, 6, 1),
        montant_ht_cents=120_000,
        montant_taxe_cents=15_924,
        montant_total_cents=135_924,
        taux_taxe_bp=1_327,
        statut=StatutAppel.PARTIEL,
    )
    session.add(appel_groupe)

    lot = LotFichier(
        reference_lot="LOT-TEST-REJETE",
        nom_fichier="COTISATIONS_OCE_202606.csv",
        type_flux=TypeFlux.COTISATIONS,
        format_fichier=FormatFichier.CSV,
        sha256="0" * 64,
        taille_octets=2_048,
        compagnie_id=None,
        periode=date(2026, 6, 1),
        date_depot=date(2026, 7, 2),
        statut=StatutLot.REJETE,
        nombre_lignes_fichier=42,
        nombre_lignes_chargees=0,
        motif_rejet="somme des lignes differente de la ligne de total",
        detecte_le=datetime(2026, 7, 2, 8, 0, 0),
    )
    session.add(lot)
    session.flush()
    session.add(
        AnomalieLot(
            lot_id=lot.id,
            ligne_numero=17,
            reference_ligne="APP-POLICE-202606",
            code=CodeAnomalie.TOTAL_INCOHERENT,
            severite=SeveriteAnomalie.BLOQUANT,
            message="le total declare ne correspond pas a la somme des lignes",
        )
    )
    session.add(
        RapprochementLigne(
            lot_id=None,
            encaissement_id=None,
            reference_bancaire="VIR-TEST-0001",
            appel_id=appel_groupe.id,
            methode=MethodeRapprochement.REFERENCE,
            statut="partiel",
            montant_encaisse_cents=100_000,
            montant_appele_cents=135_924,
            ecart_cents=35_924,
            fenetre_jours=15,
        )
    )
    session.flush()

    page = client.get("/anomalies")
    assert page.status_code == 200
    contenu = page.text

    assert "LOT-TEST-REJETE" in contenu, "l'ecran doit montrer les lots rejetes par les controles"
    assert "somme des lignes differente de la ligne de total" in contenu, (
        "le motif du rejet est ce que le gestionnaire renvoie a l'emetteur : il doit etre lisible"
    )
    assert "VIR-TEST-0001" in contenu, "l'ecran doit montrer les ecarts de rapprochement"
    assert "PC-TEST-00001" in contenu, (
        "un ecart portant sur un appel groupe doit apparaitre : la jointure interne sur contrat_id"
        " excluait les polices collectives, donc les plus gros montants du portefeuille"
    )


def test_toutes_les_reponses_d_erreur_ont_le_meme_format(client, adherent) -> None:
    """Trois familles de refus, trois chemins differents dans le code, un seul format de reponse.

    Sans cela, un client devrait savoir, route par route, s'il doit lire `erreur` ou `detail`.
    """
    cas = [
        ("contrat inconnu", client.get("/api/v1/contrats/XX-9999-99999")),
        ("adherent inconnu", client.get("/api/v1/adherents/A000000")),
        ("produit inconnu", client.get("/api/v1/produits/ZZ-INEXISTANT/delegation")),
        (
            "corps invalide",
            client.post("/api/v1/contrats", json={"numero_adherent": adherent.numero_adherent}),
        ),
    ]
    for libelle, reponse in cas:
        assert reponse.status_code >= 400, libelle
        corps = reponse.json()
        assert "erreur" in corps, f"{libelle} : la reponse ne porte pas la cle erreur, mais {sorted(corps)}"
        assert corps["erreur"]["code"], libelle
        assert corps["erreur"]["message"], libelle
