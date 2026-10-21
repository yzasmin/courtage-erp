-- Bordereau de cotisations tel que la compagnie l'a envoye. Jamais corrige.
select
    id              as brut_cotisation_id,
    lot_id,
    ligne_numero,
    reference_appel,
    numero_contrat,
    numero_adherent,
    numero_police,
    nombre_affilies,
    code_produit,
    periode_debut,
    periode_fin,
    date_echeance,
    montant_ht_cents,
    montant_taxe_cents,
    montant_total_cents
from {{ source('fichiers_recus', 'brut_cotisation') }}
