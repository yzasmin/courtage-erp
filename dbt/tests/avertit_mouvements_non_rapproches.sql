-- Severite avertissement. Un mouvement bancaire qu'aucun appel ne reclame est un point de tresorerie a
-- instruire, pas une erreur de fichier.
{{ config(severity='warn') }}
select rapprochement_id, reference_bancaire, montant_encaisse_cents
from {{ ref('stg_rapprochements') }}
where statut_rapprochement = 'non_trouve'
