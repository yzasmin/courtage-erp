select
    id                  as bordereau_id,
    reference           as reference_bordereau,
    type_bordereau,
    periode,
    date_emission,
    compagnie_id,
    apporteur_id,
    nombre_lignes,
    montant_total_cents,
    statut              as statut_bordereau
from {{ source('coeur_erp', 'bordereau') }}
