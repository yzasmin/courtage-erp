-- Reseau de distribution du cabinet : mandataires, sous-courtiers, comparateurs, salaries.
select
    id              as apporteur_id,
    code            as code_apporteur,
    nom             as nom_apporteur,
    type_apporteur,
    numero_orias,
    departement,
    date_entree,
    date_sortie,
    actif
from {{ source('coeur_erp', 'apporteur') }}
