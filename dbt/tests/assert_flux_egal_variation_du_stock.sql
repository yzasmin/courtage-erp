-- Identite stock et flux : le portefeuille de fin de mois est celui du mois precedent, plus les affaires
-- nouvelles, moins les resiliations. Si elle ne tient pas, le portefeuille et les mouvements ne
-- racontent pas la meme histoire, et le taux de resiliation (flux sur stock) ne veut plus rien dire.
with stock as (
    select date_cliche, count(*) as effectif
    from {{ ref('fct_portefeuille_mensuel') }}
    group by date_cliche
),

flux as (
    select
        (date_trunc('month', date_mouvement) + interval '1 month - 1 day')::date as date_cliche,
        sum(case when type_mouvement = 'affaire_nouvelle' then 1 else 0 end)      as entrees,
        sum(case when type_mouvement = 'resiliation' then 1 else 0 end)           as sorties
    from {{ ref('fct_mouvements_portefeuille') }}
    group by 1
),

mois as (
    select date_jour as date_cliche
    from {{ ref('dim_date') }}
    where est_dernier_jour_du_mois
),

rapproche as (
    select
        mois.date_cliche,
        coalesce(stock.effectif, 0)                                              as effectif,
        coalesce(lag(stock.effectif) over (order by mois.date_cliche), 0)        as effectif_precedent,
        coalesce(flux.entrees, 0)                                                as entrees,
        coalesce(flux.sorties, 0)                                                as sorties
    from mois
    left join stock on stock.date_cliche = mois.date_cliche
    left join flux on flux.date_cliche = mois.date_cliche
)

select *
from rapproche
where effectif <> effectif_precedent + entrees - sorties
