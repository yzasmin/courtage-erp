-- Compagnies porteuses du risque. Le cabinet place, elles assurent.
select
    id            as compagnie_id,
    code          as code_compagnie,
    raison_sociale,
    siren,
    actif
from {{ source('coeur_erp', 'compagnie') }}
