-- Remboursement servi a un adherent, quand la compagnie en a delegue la gestion.
select
    id                    as prestation_id,
    reference_prestation,
    contrat_id,
    adherent_id,
    garantie_id,
    date_soins,
    date_trunc('month', date_soins)::date as mois_soins,
    extract(year from date_soins)::int    as annee_soins,
    date_reglement,
    montant_demande_cents,
    montant_rembourse_cents,
    statut                as statut_prestation,
    motif_rejet
from {{ source('coeur_erp', 'prestation') }}
