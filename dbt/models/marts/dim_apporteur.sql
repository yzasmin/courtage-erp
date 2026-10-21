select
    apporteur_id,
    code_apporteur,
    nom_apporteur,
    type_apporteur,
    numero_orias,
    departement,
    date_entree,
    date_sortie,
    actif
from {{ ref('stg_apporteurs') }}
