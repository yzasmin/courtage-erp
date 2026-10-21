-- Indicateur 1 : ratio sinistres sur primes.
--   numerateur   : prestations REGLEES dans la periode (date de reglement), sur les produits dont la compagnie
--                  a delegue le reglement des prestations
--   denominateur : cotisations ACQUISES hors taxe de la meme periode, sur le meme perimetre de produits
-- Lecture : sur 100 euros de cotisation courue, combien ont ete rembourses.
with periodes(periode, debut, fin) as (
    values ('2024', date '2024-01-01', date '2024-12-31'),
           ('2025', date '2025-01-01', date '2025-12-31'),
           ('2026 (9 mois)', date '2026-01-01', date '2026-09-30')
),
numerateur as (
    select p.periode, sum(prestations.rembourse_euros) as prestations_reglees_euros, count(*) as nombre_de_prestations
    from periodes p
    join analytique_marts.fct_prestations prestations
      on prestations.statut_prestation = 'reglee'
     and prestations.date_reglement between p.debut and p.fin
    join analytique_marts.dim_produit produits
      on produits.produit_id = prestations.produit_id and produits.gestion_prestations_deleguee
    group by p.periode
),
denominateur as (
    select p.periode, sum(acquises.cotisation_acquise_ht_euros) as cotisations_acquises_euros
    from periodes p
    join analytique_marts.fct_cotisations_acquises acquises
      on acquises.mois_acquisition between p.debut and p.fin
    join analytique_marts.dim_produit produits
      on produits.produit_id = acquises.produit_id and produits.gestion_prestations_deleguee
    group by p.periode
)
select
    p.periode,
    round(n.prestations_reglees_euros, 2)                                       as prestations_reglees_euros,
    round(d.cotisations_acquises_euros, 2)                                      as cotisations_acquises_euros,
    round(100 * n.prestations_reglees_euros / d.cotisations_acquises_euros, 4)  as ratio_sinistres_primes_pct
from periodes p
join numerateur n using (periode)
join denominateur d using (periode)
order by p.debut;
