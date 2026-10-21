select
    id      as garantie_id,
    code    as code_garantie,
    libelle as libelle_garantie,
    famille as famille_garantie,
    rang
from {{ source('coeur_erp', 'garantie') }}
