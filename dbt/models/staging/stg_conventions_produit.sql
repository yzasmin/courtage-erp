-- Produits couverts par une convention de delegation.
select
    convention_id,
    produit_id
from {{ source('coeur_erp', 'convention_produit') }}
