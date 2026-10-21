-- Detail affilie par affilie d'un appel groupe. Sans lui, un appel groupe est une somme
-- que personne ne sait justifier.
select
    id        as ligne_appel_id,
    appel_id,
    contrat_id,
    montant_ht_cents,
    montant_taxe_cents,
    montant_total_cents
from {{ source('coeur_erp', 'ligne_appel_cotisation') }}
