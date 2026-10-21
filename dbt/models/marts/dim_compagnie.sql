select
    compagnie_id,
    code_compagnie,
    raison_sociale,
    siren,
    actif
from {{ ref('stg_compagnies') }}
