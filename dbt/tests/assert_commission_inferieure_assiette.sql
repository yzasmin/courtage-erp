-- Severite erreur. Une commission superieure a son assiette est impossible : le taux est borne a cent
-- pour cent par la contrainte de base, et une commission qui depasserait l'assiette signalerait un
-- taux mal converti.
select commission_id, assiette_cents, montant_cents, taux_bp
from {{ ref('stg_commissions') }}
where montant_cents > assiette_cents
