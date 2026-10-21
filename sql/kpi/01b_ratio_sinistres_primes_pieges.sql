-- Les pieges de l'indicateur 1, chiffres a l'appui : le meme numerateur rapporte a un mauvais denominateur
-- ou sur un mauvais perimetre.
with periodes(periode, debut, fin) as (
    values ('2024', date '2024-01-01', date '2024-12-31'),
           ('2025', date '2025-01-01', date '2025-12-31'),
           ('2026 (9 mois)', date '2026-01-01', date '2026-09-30')
),
base as (
    select
        p.periode,
        -- numerateur du perimetre delegue, en date de reglement (la reference)
        (select sum(f.rembourse_euros) from analytique_marts.fct_prestations f
           join analytique_marts.dim_produit d on d.produit_id = f.produit_id and d.gestion_prestations_deleguee
          where f.statut_prestation = 'reglee' and f.date_reglement between p.debut and p.fin) as num_reglement,
        -- meme numerateur en date de soins (survenance) : incomplet sur la fin de l'historique
        (select sum(f.rembourse_euros) from analytique_marts.fct_prestations f
           join analytique_marts.dim_produit d on d.produit_id = f.produit_id and d.gestion_prestations_deleguee
          where f.statut_prestation = 'reglee' and f.date_soins between p.debut and p.fin) as num_soins,
        -- denominateur de reference : acquis, perimetre delegue
        (select sum(a.cotisation_acquise_ht_euros) from analytique_marts.fct_cotisations_acquises a
           join analytique_marts.dim_produit d on d.produit_id = a.produit_id and d.gestion_prestations_deleguee
          where a.mois_acquisition between p.debut and p.fin) as den_acquis,
        -- piege 1 : cotisations EMISES (echeance dans la periode) au lieu d'acquises
        (select sum(c.cotisation_ht_euros) from analytique_marts.fct_cotisations c
           join analytique_marts.dim_produit d on d.produit_id = c.produit_id and d.gestion_prestations_deleguee
          where c.date_echeance between p.debut and p.fin) as den_emis,
        -- piege 2 : acquises de TOUS les produits, prevoyance comprise
        (select sum(a.cotisation_acquise_ht_euros) from analytique_marts.fct_cotisations_acquises a
          where a.mois_acquisition between p.debut and p.fin) as den_tous_produits,
        -- piege 3 : cotisations TTC emises
        (select sum(c.cotisation_ttc_euros) from analytique_marts.fct_cotisations c
           join analytique_marts.dim_produit d on d.produit_id = c.produit_id and d.gestion_prestations_deleguee
          where c.date_echeance between p.debut and p.fin) as den_ttc_emis
    from periodes p
)
select
    periode,
    round(100 * num_reglement / den_acquis, 2)        as reference_pct,
    round(100 * num_soins / den_acquis, 2)            as en_date_de_soins_pct,
    round(100 * num_reglement / den_emis, 2)          as sur_emises_pct,
    round(100 * num_reglement / den_tous_produits, 2) as sur_tous_produits_pct,
    round(100 * num_reglement / den_ttc_emis, 2)      as sur_ttc_emis_pct,
    round(den_acquis, 2)                              as cotisations_acquises_euros,
    round(den_emis, 2)                                as cotisations_emises_euros
from base
order by periode;
