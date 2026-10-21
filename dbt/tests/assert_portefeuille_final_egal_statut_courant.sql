-- Le dernier cliche doit retrouver, contrat par contrat, ce que dit le statut courant du contrat. Les deux
-- viennent de la meme table d'avenants par deux chemins differents : l'un relit l'historique, l'autre le
-- dernier etat. S'ils divergent, la reconstitution des versions est fausse.
with dernier as (
    select max(date_cliche) as date_cliche from {{ ref('fct_portefeuille_mensuel') }}
),

par_cliche as (
    select portefeuille.contrat_id
    from {{ ref('fct_portefeuille_mensuel') }} as portefeuille
    join dernier on dernier.date_cliche = portefeuille.date_cliche
),

par_statut as (
    select contrat_id
    from {{ ref('stg_contrats') }}
    where statut_contrat in ('en_cours', 'suspendu')
      and date_effet <= (select date_cliche from dernier)
)

select coalesce(par_cliche.contrat_id, par_statut.contrat_id) as contrat_id
from par_cliche
full outer join par_statut on par_statut.contrat_id = par_cliche.contrat_id
where par_cliche.contrat_id is null or par_statut.contrat_id is null
