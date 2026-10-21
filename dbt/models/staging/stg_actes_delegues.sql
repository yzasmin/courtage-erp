-- Actes de gestion confies au cabinet par une convention : quittancement, encaissement, prestations...
select
    convention_id,
    acte
from {{ source('coeur_erp', 'acte_delegue') }}
