select
    id      as branche_id,
    code    as code_branche,
    libelle as libelle_branche,
    famille as famille_branche
from {{ source('coeur_erp', 'branche') }}
