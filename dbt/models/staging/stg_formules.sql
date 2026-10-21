select
    id        as formule_id,
    produit_id,
    code      as code_formule,
    libelle   as libelle_formule,
    niveau,
    tarif_base_mensuel_cents
from {{ source('coeur_erp', 'formule') }}
