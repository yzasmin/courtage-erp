-- Plafond annuel de chaque garantie pour chaque formule, quand il est saisi.
select
    id                    as formule_garantie_id,
    formule_id,
    garantie_id,
    libelle_couverture,
    taux_remboursement_bp,
    plafond_annuel_cents
from {{ source('coeur_erp', 'formule_garantie') }}
