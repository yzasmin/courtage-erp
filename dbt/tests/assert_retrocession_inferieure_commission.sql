-- Severite erreur. Le cabinet ne peut pas reverser plus que la commission qu'il a recue.
select
    retrocessions.retrocession_id,
    retrocessions.montant_cents as retrocession_cents,
    commissions.montant_cents   as commission_cents
from {{ ref('stg_retrocessions') }} as retrocessions
join {{ ref('stg_commissions') }} as commissions
  on commissions.commission_id = retrocessions.commission_id
where retrocessions.montant_cents > commissions.montant_cents
