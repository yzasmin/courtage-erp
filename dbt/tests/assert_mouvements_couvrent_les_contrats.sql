-- Chaque contrat hors devis a exactement une affaire nouvelle, et chaque contrat resilie exactement une
-- resiliation. Un devis n'a aucun mouvement.
with attendu as (
    select
        contrat_id,
        case when statut_contrat <> 'devis' then 1 else 0 end as affaires,
        case when statut_contrat = 'resilie' then 1 else 0 end as resiliations
    from {{ ref('stg_contrats') }}
),

constate as (
    select
        contrat_id,
        sum(case when type_mouvement = 'affaire_nouvelle' then 1 else 0 end) as affaires,
        sum(case when type_mouvement = 'resiliation' then 1 else 0 end)      as resiliations
    from {{ ref('fct_mouvements_portefeuille') }}
    group by contrat_id
)

select attendu.contrat_id
from attendu
left join constate on constate.contrat_id = attendu.contrat_id
where attendu.affaires <> coalesce(constate.affaires, 0)
   or attendu.resiliations <> coalesce(constate.resiliations, 0)
