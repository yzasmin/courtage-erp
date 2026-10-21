select
    id          as taux_retrocession_id,
    apporteur_id,
    produit_id,
    taux_bp,
    date_debut_validite,
    date_fin_validite
from {{ source('coeur_erp', 'taux_retrocession') }}
