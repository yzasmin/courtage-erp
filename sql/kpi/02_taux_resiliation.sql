-- Indicateur 2 : taux de resiliation.
--   numerateur   : resiliations prenant effet dans la periode, sur des contrats DEJA au portefeuille au
--                  premier jour de la periode (date d'effet du contrat anterieure au debut)
--   denominateur : contrats au portefeuille la veille du premier jour de la periode (cliche de fin du mois
--                  precedent), suspendus compris
-- Le taux annualise ramene lineairement la periode a 365 jours : il n'a de sens que pour une periode
-- plus courte qu'un an.
with periodes(periode, debut, fin) as (
    values ('2024', date '2024-01-01', date '2024-12-31'),
           ('2025', date '2025-01-01', date '2025-12-31'),
           ('2026 (9 mois)', date '2026-01-01', date '2026-09-30')
),
effectif_debut as (
    select p.periode, count(*) as contrats_au_portefeuille_en_debut_de_periode
    from periodes p
    join analytique_marts.fct_portefeuille_mensuel f on f.date_cliche = p.debut - 1
    group by p.periode
),
resiliations as (
    select p.periode, count(*) as resiliations_de_la_cohorte
    from periodes p
    join analytique_marts.fct_mouvements_portefeuille m
      on m.type_mouvement = 'resiliation'
     and m.date_mouvement between p.debut and p.fin
     and m.date_effet_contrat < p.debut
    group by p.periode
)
select
    p.periode,
    r.resiliations_de_la_cohorte,
    e.contrats_au_portefeuille_en_debut_de_periode,
    round(100.0 * r.resiliations_de_la_cohorte / e.contrats_au_portefeuille_en_debut_de_periode, 4) as taux_resiliation_pct,
    (p.fin - p.debut + 1)                                                                          as jours_de_la_periode,
    round(100.0 * r.resiliations_de_la_cohorte / e.contrats_au_portefeuille_en_debut_de_periode
          * 365 / (p.fin - p.debut + 1), 4)                                                        as taux_annualise_pct
from periodes p
join effectif_debut e using (periode)
join resiliations r using (periode)
order by p.debut;
