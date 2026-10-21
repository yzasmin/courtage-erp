-- Chaque avenant est une version du contrat. L'etat a une date est le dernier avenant en vigueur.
select
    id            as avenant_id,
    contrat_id,
    numero_ordre,
    type_avenant,
    date_effet,
    date_saisie,
    statut        as statut_apres_avenant,
    formule_id,
    apporteur_id,
    cotisation_mensuelle_cents,
    fractionnement,
    motif_resiliation
from {{ source('coeur_erp', 'avenant') }}
