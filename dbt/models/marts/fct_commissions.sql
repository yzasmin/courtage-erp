-- Fait commissions : ce que la compagnie doit au cabinet, et ce que le cabinet reverse a l'apporteur.
--
-- Le taux figé au calcul est conserve, et non relu du bareme : un bordereau doit rester explicable
-- apres un changement de bareme.

select
    commissions.commission_id,
    commissions.appel_id,
    appels.reference_appel,
    appels.numero_porteur,
    commissions.contrat_id,
    commissions.police_id,
    commissions.compagnie_id,
    commissions.produit_id,
    appels.branche_id,
    retrocessions.apporteur_id,
    commissions.periode,
    appels.date_echeance,
    commissions.taux_bp                                        as taux_commission_bp,
    retrocessions.taux_bp                                      as taux_retrocession_bp,
    (commissions.assiette_cents / 100.0)::numeric(14, 2)       as assiette_euros,
    (commissions.montant_cents / 100.0)::numeric(14, 2)        as commission_euros,
    (coalesce(retrocessions.montant_cents, 0) / 100.0)::numeric(14, 2) as retrocession_euros,
    ((commissions.montant_cents - coalesce(retrocessions.montant_cents, 0)) / 100.0)::numeric(14, 2)
        as marge_cabinet_euros,
    commissions.assiette_cents,
    commissions.montant_cents                                  as commission_cents,
    coalesce(retrocessions.montant_cents, 0)                   as retrocession_cents,
    commissions.bordereau_id                                   as bordereau_commission_id,
    retrocessions.bordereau_id                                 as bordereau_retrocession_id
from {{ ref('stg_commissions') }} as commissions
join {{ ref('int_appels_enrichis') }} as appels on appels.appel_id = commissions.appel_id
left join {{ ref('stg_retrocessions') }} as retrocessions
  on retrocessions.commission_id = commissions.commission_id
