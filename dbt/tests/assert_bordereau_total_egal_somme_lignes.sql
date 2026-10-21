-- Severite erreur. Le total d'un bordereau doit egaler la somme de ses lignes, au centime. C'est la
-- seule anomalie qu'un apporteur ou une compagnie remarque immediatement.
with commissions_par_bordereau as (
    select bordereau_id, count(*) as lignes, sum(montant_cents) as total_cents
    from {{ ref('stg_commissions') }}
    where bordereau_id is not null
    group by bordereau_id
),

retrocessions_par_bordereau as (
    select bordereau_id, count(*) as lignes, sum(montant_cents) as total_cents
    from {{ ref('stg_retrocessions') }}
    where bordereau_id is not null
    group by bordereau_id
),

lignes as (
    select * from commissions_par_bordereau
    union all
    select * from retrocessions_par_bordereau
)

select
    bordereaux.bordereau_id,
    bordereaux.reference_bordereau,
    bordereaux.nombre_lignes,
    lignes.lignes          as lignes_reelles,
    bordereaux.montant_total_cents,
    lignes.total_cents     as total_reel_cents
from {{ ref('stg_bordereaux') }} as bordereaux
join lignes on lignes.bordereau_id = bordereaux.bordereau_id
where bordereaux.montant_total_cents <> lignes.total_cents
   or bordereaux.nombre_lignes <> lignes.lignes
