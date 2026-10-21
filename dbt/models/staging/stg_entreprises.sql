select
    id             as entreprise_id,
    siren,
    raison_sociale,
    code_naf,
    effectif,
    departement,
    date_adhesion
from {{ source('coeur_erp', 'entreprise_souscriptrice') }}
