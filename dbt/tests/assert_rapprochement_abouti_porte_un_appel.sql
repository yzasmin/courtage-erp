-- Severite erreur. Un rapprochement declare abouti sans appel, ou sans methode, laisserait croire a un
-- encaissement rattache a rien.
select rapprochement_id, reference_bancaire, statut_rapprochement, methode, appel_id
from {{ ref('stg_rapprochements') }}
where est_abouti and (appel_id is null or methode = 'aucune')
