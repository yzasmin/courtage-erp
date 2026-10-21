-- Quittancement : ce que le cabinet a appele, aupres d'un adherent ou d'une entreprise.
select
    id                   as appel_id,
    reference_appel,
    contrat_id,
    police_id,
    coalesce(nombre_affilies, 1) as nombre_affilies,
    police_id is not null        as est_un_appel_groupe,
    periode_debut,
    periode_fin,
    date_echeance,
    date_trunc('month', date_echeance)::date as mois_echeance,
    montant_ht_cents,
    montant_taxe_cents,
    montant_total_cents,
    taux_taxe_bp,
    statut               as statut_appel,
    bordereau_id
from {{ source('coeur_erp', 'appel_cotisation') }}
