select
    id           as produit_id,
    code         as code_produit,
    libelle      as libelle_produit,
    branche_id,
    compagnie_id,
    date_ouverture,
    date_fermeture
from {{ source('coeur_erp', 'produit') }}
