-- Convention de delegation de gestion : ce que la compagnie confie au cabinet, et pour quelle duree.
select
    id                  as convention_id,
    reference           as reference_convention,
    compagnie_id,
    portee,
    date_debut_validite,
    date_fin_validite
from {{ source('coeur_erp', 'convention_delegation') }}
