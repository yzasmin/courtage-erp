-- Table de dates, construite sur l'amplitude reelle du portefeuille et des flux.
--
-- Bornee par les donnees et non par des annees ecrites en dur : une dimension qui s'arrete avant le
-- dernier fait produit des agregats muets, et une dimension qui va jusqu'en 2050 encombre le modele.
-- Le debut est celui du premier avenant pris effet (le portefeuille est anterieur a la fenetre de
-- quittancement), la fin est le dernier jour du mois du dernier fait observe : c'est la date d'arret
-- de l'historique, reprise par les autres marts.

with bornes as (
    select
        least(
            (select min(date_effet) from {{ ref('stg_avenants') }} where numero_ordre >= 1),
            (select min(date_soins) from {{ ref('stg_prestations') }}),
            (select min(date_echeance) from {{ ref('stg_appels_cotisation') }})
        ) as debut,
        greatest(
            (select max(date_effet) from {{ ref('stg_avenants') }}),
            (select max(date_soins) from {{ ref('stg_prestations') }}),
            (select max(date_reglement) from {{ ref('stg_prestations') }}),
            (select max(date_echeance) from {{ ref('stg_appels_cotisation') }})
        ) as fin
),

jours as (
    select generate_series(
        date_trunc('month', (select debut from bornes))::date,
        (date_trunc('month', (select fin from bornes)) + interval '1 month - 1 day')::date,
        interval '1 day'
    )::date as jour
)

select
    jour                                         as date_jour,
    extract(year from jour)::int                 as annee,
    extract(quarter from jour)::int              as trimestre,
    extract(month from jour)::int                as mois,
    to_char(jour, 'YYYY-MM')                     as annee_mois,
    extract(year from jour)::int || '-T' || extract(quarter from jour)::int as annee_trimestre,
    date_trunc('month', jour)::date              as premier_jour_du_mois,
    (date_trunc('month', jour) + interval '1 month - 1 day')::date as dernier_jour_du_mois,
    jour = (date_trunc('month', jour) + interval '1 month - 1 day')::date as est_dernier_jour_du_mois,
    extract(isodow from jour)::int               as jour_de_semaine,
    extract(isodow from jour)::int in (6, 7)     as est_week_end
from jours
