-- Sur les appels dont la periode est entierement ecoulee a la date d'arret, la somme des parts acquises
-- doit egaler le montant hors taxe appele, au centime pres. Un ecart signale une periode mal bornee ou
-- un mois perdu dans la repartition.
with arret as (
    select max(date_jour) as date_arret from {{ ref('dim_date') }}
),

acquis as (
    select appel_id, sum(cotisation_acquise_ht_euros) as acquis_euros
    from {{ ref('fct_cotisations_acquises') }}
    group by appel_id
)

select
    appels.appel_id,
    appels.cotisation_ht_euros,
    acquis.acquis_euros
from {{ ref('fct_cotisations') }} as appels
cross join arret
left join acquis on acquis.appel_id = appels.appel_id
where appels.periode_fin <= arret.date_arret
  and abs(appels.cotisation_ht_euros - coalesce(acquis.acquis_euros, 0)) > 0.005
