-- Part de commission reversee a l'apporteur qui a amene l'affaire.
select
    id            as retrocession_id,
    commission_id,
    apporteur_id,
    periode,
    assiette_cents,
    taux_bp,
    montant_cents,
    bordereau_id
from {{ source('coeur_erp', 'retrocession') }}
