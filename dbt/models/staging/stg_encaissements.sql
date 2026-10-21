-- Mouvement bancaire. `appel_id` nul signifie non rapproche, ce qui est une anomalie a traiter
-- et non une donnee invalide.
select
    id                   as encaissement_id,
    reference_bancaire,
    appel_id,
    contrat_id,
    date_encaissement,
    date_trunc('month', date_encaissement)::date as mois_encaissement,
    montant_cents,
    moyen,
    statut_rapprochement,
    libelle_releve
from {{ source('coeur_erp', 'encaissement') }}
