-- Releve bancaire tel que la banque l'a envoye.
select
    id              as brut_encaissement_id,
    lot_id,
    ligne_numero,
    reference_bancaire,
    reference_appel,
    numero_contrat,
    numero_police,
    date_encaissement,
    montant_cents,
    moyen,
    libelle,
    reference_appel is null as sans_reference_appel
from {{ source('fichiers_recus', 'brut_encaissement') }}
