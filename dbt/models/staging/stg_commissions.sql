-- Commission due par la compagnie au cabinet, une par appel de cotisation.
select
    id            as commission_id,
    appel_id,
    contrat_id,
    police_id,
    compagnie_id,
    produit_id,
    periode,
    assiette_cents,
    taux_bp,
    montant_cents,
    bordereau_id
from {{ source('coeur_erp', 'commission') }}
