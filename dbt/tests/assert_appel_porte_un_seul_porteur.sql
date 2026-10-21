-- Severite erreur. Un appel s'adresse a un contrat ou a une police, jamais aux deux, jamais a aucun.
select appel_id, reference_appel, contrat_id, police_id
from {{ ref('stg_appels_cotisation') }}
where (contrat_id is null and police_id is null)
   or (contrat_id is not null and police_id is not null)
