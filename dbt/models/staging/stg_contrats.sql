-- Contrat individuel, ou bulletin d'affiliation d'un salarie a une police collective.
select
    id                 as contrat_id,
    numero_contrat,
    adherent_id,
    entreprise_id,
    produit_id,
    police_id,
    statut             as statut_contrat,
    date_souscription,
    date_effet,
    date_resiliation,
    motif_resiliation,
    formule_id,
    apporteur_id,
    cotisation_mensuelle_cents,
    fractionnement,
    police_id is not null as est_une_affiliation
from {{ source('coeur_erp', 'contrat') }}
