-- Table de dates, construite sur l'amplitude reelle des flux du portefeuille.
--
-- Bornee par les donnees et non par des annees ecrites en dur : une dimension qui s'arrete avant le
-- dernier fait produit des agregats muets, et une dimension qui va jusqu'en 2050 encombre le modele.

with bornes as (
    select
        least(min(date_echeance), min(mois_echeance)) as debut,
        max(date_echeance)                            as fin
    from {{ ref('stg_appels_cotisation') }}
),

jours as (
    select generate_series(
        date_trunc('month', (select debut from bornes))::date,
        (select fin from bornes),
        interval '1 day'
    )::date as jour
)

select
    jour                                         as date_jour,
    extract(year from jour)::int                 as annee,
    extract(quarter from jour)::int              as trimestre,
    extract(month from jour)::int                as mois,
    to_char(jour, 'YYYY-MM')                     as annee_mois,
    date_trunc('month', jour)::date              as premier_jour_du_mois,
    (date_trunc('month', jour) + interval '1 month - 1 day')::date as dernier_jour_du_mois,
    extract(isodow from jour)::int               as jour_de_semaine,
    extract(isodow from jour)::int in (6, 7)     as est_week_end
from jours
