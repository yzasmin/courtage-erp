-- Les pieges de l'indicateur 2, chiffres a l'appui.
with periodes(periode, debut, fin) as (
    values ('2024', date '2024-01-01', date '2024-12-31'),
           ('2025', date '2025-01-01', date '2025-12-31'),
           ('2026 (9 mois)', date '2026-01-01', date '2026-09-30')
),
base as (
    select
        p.periode,
        (select count(*) from analytique_marts.fct_portefeuille_mensuel f where f.date_cliche = p.debut - 1) as effectif_debut,
        (select count(*) from analytique_marts.fct_portefeuille_mensuel f where f.date_cliche = p.fin)       as effectif_fin,
        (select count(*) from analytique_marts.fct_mouvements_portefeuille m
          where m.type_mouvement = 'resiliation' and m.date_mouvement between p.debut and p.fin
            and m.date_effet_contrat < p.debut)                                                              as resiliations_cohorte,
        (select count(*) from analytique_marts.fct_mouvements_portefeuille m
          where m.type_mouvement = 'resiliation' and m.date_mouvement between p.debut and p.fin)             as resiliations_toutes
    from periodes p
)
select
    periode,
    effectif_debut,
    effectif_fin,
    resiliations_cohorte,
    resiliations_toutes,
    resiliations_toutes - resiliations_cohorte                                        as nees_et_resiliees_dans_la_periode,
    round(100.0 * resiliations_cohorte / effectif_debut, 4)                           as reference_pct,
    round(100.0 * resiliations_toutes / effectif_debut, 4)                            as toutes_resiliations_pct,
    round(100.0 * resiliations_cohorte / effectif_fin, 4)                             as sur_effectif_de_fin_pct,
    round(100.0 * resiliations_cohorte / ((effectif_debut + effectif_fin) / 2.0), 4)  as sur_effectif_moyen_pct
from base
order by periode;
