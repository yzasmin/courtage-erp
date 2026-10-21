select
    id              as brut_prestation_id,
    lot_id,
    ligne_numero,
    reference_prestation,
    numero_contrat,
    numero_adherent,
    code_garantie,
    date_soins,
    montant_demande_cents,
    montant_rembourse_cents
from {{ source('fichiers_recus', 'brut_prestation') }}
