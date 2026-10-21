-- Police collective : le contrat cadre souscrit par une entreprise pour ses salaries.
select
    id            as police_id,
    numero_police,
    entreprise_id,
    produit_id,
    formule_socle_id,
    apporteur_id,
    statut        as statut_police,
    date_souscription,
    date_effet,
    date_resiliation,
    motif_resiliation,
    fractionnement
from {{ source('coeur_erp', 'police_collective') }}
