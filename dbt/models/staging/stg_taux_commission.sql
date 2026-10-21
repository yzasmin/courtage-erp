-- Bareme date. Le calcul applique le taux en vigueur a la date d'echeance de l'appel.
select
    id          as taux_commission_id,
    produit_id,
    taux_bp,
    assiette,
    date_debut_validite,
    date_fin_validite
from {{ source('coeur_erp', 'taux_commission') }}
