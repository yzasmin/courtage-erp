-- Branche d'assurance : sante individuelle, sante collective, prevoyance.
-- Le modele de produit est parametre par branche, donc une branche de plus est une ligne de plus.
select
    branche_id,
    code_branche,
    libelle_branche,
    famille_branche
from {{ ref('stg_branches') }}
