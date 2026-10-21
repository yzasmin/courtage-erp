"""Controles de cohérence métier sur le jeu de démonstration, exécutés contre la base générée.

Ce script ne teste pas du code : il interroge les **données** et vérifie qu'elles décrivent un cabinet
de courtage plausible. C'est le genre de contrôle qu'un gestionnaire ferait en ouvrant l'outil, et
chaque ligne correspond à un défaut qui a réellement été trouvé puis corrigé.

Il sort en échec dès qu'un contrôle est rouge, ce qui le rend utilisable en intégration continue.

Usage : `python -m uv run python scripts/preuve_coherence_metier.py`
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import text

from courtage.config import RACINE_PROJET
from courtage.db import cree_moteur


@dataclass(frozen=True, slots=True)
class Controle:
    """Un contrôle métier : sa question, sa requête, et ce qu'elle doit renvoyer."""

    code: str
    question: str
    requete: str
    attendu: int = 0
    #: Quand il est faux, le contrôle vérifie que le compte est strictement supérieur à `attendu`.
    doit_etre_nul: bool = True
    #: Nom d'une règle évaluée en Python sur les lignes rendues, quand le SQL ne serait pas portable.
    compte_en_python: str | None = None


#: Fragment commun aux deux contrôles de plafond. Il reconstitue, prestation par prestation, le plafond
#: de la formule en vigueur à la date des soins, puis le cumul déjà remboursé **avant** elle dans l'ordre
#: des dates. L'année est extraite par `substr` sur la date convertie en texte, seule forme qui donne le
#: même résultat sur SQLite, où la date est stockée en texte, et sur PostgreSQL, où elle est typée.
#: La fonction de fenêtre est supportée par les deux moteurs.
PLAFOND_CHRONOLOGIQUE = """
with base as (
  select pr.id, pr.contrat_id, pr.garantie_id, pr.date_soins, pr.statut, pr.motif_rejet,
         pr.montant_rembourse_cents,
         substr(cast(pr.date_soins as char(10)), 1, 4) as annee,
         (select a.formule_id from avenant a
           where a.contrat_id = pr.contrat_id and a.date_effet <= pr.date_soins
           order by a.date_effet desc, a.numero_ordre desc limit 1) as formule_id
    from prestation pr
),
avec_plafond as (
  select b.id, b.contrat_id, b.garantie_id, b.date_soins, b.statut, b.motif_rejet,
         b.montant_rembourse_cents, b.annee, fg.plafond_annuel_cents as plafond
    from base b
    join formule_garantie fg on fg.formule_id = b.formule_id and fg.garantie_id = b.garantie_id
   where fg.plafond_annuel_cents is not null
),
avec_cumul as (
  select avec_plafond.*,
         coalesce(sum(case when statut = 'reglee' then montant_rembourse_cents else 0 end) over (
             partition by contrat_id, garantie_id, annee
             order by date_soins, id
             rows between unbounded preceding and 1 preceding), 0) as deja_rembourse
    from avec_plafond
)
"""

CONTROLES: tuple[Controle, ...] = (
    Controle(
        "affiliation_sans_police",
        "Toute affiliation collective est rattachée à une police",
        """select count(*) from contrat c
           join produit p on p.id = c.produit_id
           join branche b on b.id = p.branche_id
           where b.code = 'SC' and c.police_id is null""",
    ),
    Controle(
        "appel_individuel_sur_collectif",
        "Aucune affiliation collective n'est quittancée pour elle-même",
        """select count(*) from appel_cotisation a
           join contrat c on c.id = a.contrat_id
           where c.police_id is not null""",
    ),
    Controle(
        "appel_groupe_sans_ligne",
        "Tout appel groupé porte le détail de ses affiliés",
        """select count(*) from appel_cotisation a
           left join ligne_appel_cotisation l on l.appel_id = a.id
           where a.police_id is not null and l.id is null""",
    ),
    Controle(
        "total_appel_groupe_faux",
        "Le total d'un appel groupé égale la somme de ses lignes",
        """select count(*) from (
             select a.id, a.montant_total_cents as total, sum(l.montant_total_cents) as somme
             from appel_cotisation a
             join ligne_appel_cotisation l on l.appel_id = a.id
             group by a.id, a.montant_total_cents
           ) t where t.total <> t.somme""",
    ),
    Controle(
        "affilies_mal_comptes",
        "Le nombre d'affiliés annoncé par un appel groupé égale son nombre de lignes",
        """select count(*) from (
             select a.id, a.nombre_affilies as annonce, count(l.id) as reel
             from appel_cotisation a
             join ligne_appel_cotisation l on l.appel_id = a.id
             group by a.id, a.nombre_affilies
           ) t where t.annonce <> t.reel""",
    ),
    Controle(
        "prestation_pendant_suspension",
        "Aucune prestation n'est servie pendant une suspension de garanties, ouverte ou refermée",
        # La jointure sur « l'avenant suivant » était interne, et c'était le défaut : les 36 contrats
        # dont la suspension est encore ouverte à la fin de l'historique n'avaient pas d'avenant
        # suivant, le contrôle les ignorait donc entièrement. Il restait six prestations servies
        # pendant une suspension en cours, dont une réglée, et la preuve les annonçait à zéro.
        # Jointure externe, et absence de successeur lue comme une suspension sans fin connue.
        """select count(*) from prestation pr
           join avenant av on av.contrat_id = pr.contrat_id and av.statut = 'suspendu'
           left join avenant suite on suite.contrat_id = av.contrat_id
                                  and suite.numero_ordre = av.numero_ordre + 1
           where pr.date_soins >= av.date_effet
             and (suite.date_effet is null or pr.date_soins < suite.date_effet)""",
    ),
    Controle(
        "rejet_plafond_premature",
        "Un rejet pour plafond atteint tombe à une date où le plafond est réellement consommé",
        # Le générateur cumulait le plafond dans l'ordre de génération, et les soins sont tirés au
        # hasard dans la fenêtre de garantie : 55 pour cent des rejets pour plafond atteint tombaient
        # à une date où rien n'avait encore été remboursé. Ce contrôle relit le cumul dans l'ordre des
        # dates, avec le plafond de la formule en vigueur à la date des soins.
        PLAFOND_CHRONOLOGIQUE
        + """select count(*) from avec_cumul
           where motif_rejet = 'plafond annuel de la garantie atteint'
             and deja_rembourse < plafond""",
    ),
    Controle(
        "remboursement_au_dela_du_reste",
        "Aucun remboursement ne dépasse le reste de plafond à la date des soins",
        PLAFOND_CHRONOLOGIQUE
        + """select count(*) from avec_cumul
           where statut = 'reglee'
             and montant_rembourse_cents > plafond - deja_rembourse""",
    ),
    Controle(
        "prestation_apres_resiliation",
        "Aucune prestation n'est servie après la résiliation du contrat",
        """select count(*) from prestation pr
           join contrat c on c.id = pr.contrat_id
           where c.date_resiliation is not null and pr.date_soins >= c.date_resiliation""",
    ),
    Controle(
        "plafond_annuel_depasse",
        "Le cumul remboursé ne dépasse pas le plafond de la formule en vigueur aux soins",
        """with servies as (
             select pr.contrat_id, pr.garantie_id, pr.date_soins, pr.montant_rembourse_cents,
                    (select a.formule_id from avenant a
                      where a.contrat_id = pr.contrat_id and a.date_effet <= pr.date_soins
                      order by a.date_effet desc, a.numero_ordre desc limit 1) as formule_id
             from prestation pr where pr.statut = 'reglee'
           )
           select count(*) from (
             select s.contrat_id, s.garantie_id, substr(cast(s.date_soins as char(10)), 1, 4) as annee,
                    sum(s.montant_rembourse_cents) as cumul,
                    max(fg.plafond_annuel_cents) as plafond
             from servies s
             join formule_garantie fg on fg.formule_id = s.formule_id
                                     and fg.garantie_id = s.garantie_id
             where fg.plafond_annuel_cents is not null
             group by s.contrat_id, s.garantie_id, annee
           ) t where t.cumul > t.plafond""",
    ),
    Controle(
        "infra_annuelle_trop_tot",
        "Aucune résiliation infra-annuelle avant douze mois d'ancienneté",
        # L'ecart entre deux dates ne s'ecrit pas de la meme facon sur les deux moteurs : `julianday`
        # est propre a SQLite, et l'arithmetique d'intervalle est propre a PostgreSQL. La comparaison
        # est donc faite en Python, sur les seules lignes concernees, qui sont peu nombreuses.
        """select date_effet, date_resiliation from contrat
           where motif_resiliation = 'infra_annuelle'""",
        compte_en_python="anciennete_inferieure_a_un_an",
    ),
    Controle(
        "appel_encaisse_sans_encaissement",
        "Aucun appel encaissé ou partiel sans ligne d'encaissement",
        """select count(*) from appel_cotisation a
           left join encaissement e on e.appel_id = a.id
           where a.statut in ('encaisse', 'partiel') and e.id is null""",
    ),
    Controle(
        "avenant_hors_ordre",
        "Les dates d'effet des avenants croissent avec leur rang",
        """select count(*) from avenant a
           join avenant b on b.contrat_id = a.contrat_id and b.numero_ordre = a.numero_ordre + 1
           where b.date_effet < a.date_effet""",
    ),
    Controle(
        "cache_contrat_faux",
        "Le cache du contrat égale la reconstitution par les avenants",
        """with dernier as (
             select a.contrat_id, a.statut, a.formule_id, a.apporteur_id,
                    a.cotisation_mensuelle_cents,
                    row_number() over (partition by a.contrat_id
                                       order by a.date_effet desc, a.numero_ordre desc) rn
             from avenant a
           )
           select count(*) from contrat c
           join dernier d on d.contrat_id = c.id and d.rn = 1
           where c.statut <> d.statut or c.formule_id <> d.formule_id
              or c.apporteur_id <> d.apporteur_id
              or c.cotisation_mensuelle_cents <> d.cotisation_mensuelle_cents""",
    ),
    Controle(
        "avenant_sans_auteur",
        "Tout avenant porte l'auteur de sa saisie",
        "select count(*) from avenant where auteur is null or auteur = ''",
    ),
    Controle(
        "quittancement_apres_convention_echue",
        "Aucun appel émis après l'expiration de la convention de délégation",
        """select count(*) from appel_cotisation a
           join contrat c on c.id = a.contrat_id
           join convention_produit cp on cp.produit_id = c.produit_id
           join convention_delegation cd on cd.id = cp.convention_id
           where cd.date_fin_validite is not null
             and a.date_echeance > cd.date_fin_validite""",
    ),
    Controle(
        "portefeuille_initial",
        "Le portefeuille est déjà constitué à l'ouverture de l'historique",
        """select count(*) from contrat
           where date_effet <= '2024-01-01'
             and (date_resiliation is null or date_resiliation > '2024-01-01')""",
        attendu=2_000,
        doit_etre_nul=False,
    ),
    Controle(
        "convention_echue_presente",
        "Une convention arrivée à échéance existe, pour rendre le refus constatable",
        "select count(*) from convention_delegation where date_fin_validite is not null",
        attendu=0,
        doit_etre_nul=False,
    ),
)


def _en_date(valeur: object) -> date | None:
    """Normalise une valeur de date rendue par une requete brute.

    PostgreSQL rend un objet `date`, SQLite rend la chaine `AAAA-MM-JJ`. Sans cette normalisation, le
    controle fonctionne sur un moteur et tombe sur l'autre, ce qui est precisement le genre d'ecart
    que ce script existe pour attraper.
    """
    if valeur is None:
        return None
    if isinstance(valeur, date):
        return valeur
    return date.fromisoformat(str(valeur)[:10])


def _compte_en_python(regle: str, lignes: list) -> int:
    """Applique une regle que le SQL n'exprimerait pas de la meme facon sur les deux moteurs."""
    if regle == "anciennete_inferieure_a_un_an":
        total = 0
        for brut_effet, brut_resiliation in lignes:
            date_effet = _en_date(brut_effet)
            date_resiliation = _en_date(brut_resiliation)
            if date_effet is None or date_resiliation is None:
                continue
            anciennete_mois = (date_resiliation.year - date_effet.year) * 12 + (
                date_resiliation.month - date_effet.month
            )
            if (date_resiliation.day < date_effet.day) and anciennete_mois > 0:
                anciennete_mois -= 1
            if anciennete_mois < 12:
                total += 1
        return total
    raise ValueError(f"regle de comptage inconnue : {regle}")


def main() -> int:
    moteur = cree_moteur(echo=False)
    resultats: list[dict] = []
    echecs = 0

    try:
        with moteur.connect() as connexion:
            for controle in CONTROLES:
                if controle.compte_en_python:
                    lignes = connexion.execute(text(controle.requete)).all()
                    compte = _compte_en_python(controle.compte_en_python, lignes)
                else:
                    compte = connexion.execute(text(controle.requete)).scalar() or 0
                if controle.doit_etre_nul:
                    conforme = compte == controle.attendu
                    detail = f"{compte} ligne(s), attendu {controle.attendu}"
                else:
                    conforme = compte > controle.attendu
                    detail = f"{compte} ligne(s), attendu plus de {controle.attendu}"
                resultats.append(
                    {
                        "code": controle.code,
                        "question": controle.question,
                        "compte": int(compte),
                        "conforme": conforme,
                    }
                )
                marque = "ok    " if conforme else "ECHEC "
                if not conforme:
                    echecs += 1
                print(f"  {marque} {controle.question}\n           {detail}")
    finally:
        moteur.dispose()

    rapport = {
        "mesure_le": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "controles": len(CONTROLES),
        "echecs": echecs,
        "conforme": echecs == 0,
        "detail": resultats,
    }
    dossier = RACINE_PROJET / "results"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / "coherence_metier.json"
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    if echecs == 0:
        print(f"CONFORME : {len(CONTROLES)} controles de coherence metier passes")
    else:
        print(f"NON CONFORME : {echecs} controle(s) sur {len(CONTROLES)}", file=sys.stderr)
    print(f"rapport : {chemin}")
    return 0 if echecs == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
