-- Severite erreur. Une commission dont l'assiette est la cotisation encaissee doit s'appuyer sur un
-- encaissement reellement rapproche. Commissionner une cotisation que personne n'a payee produirait un
-- bordereau que la compagnie refuserait. Hors du cas D24 : quand la compagnie encaisse elle-meme, le
-- cabinet est commissionne sur la cotisation appelee et n'a aucun encaissement a rapprocher.
select
    commissions.commission_id,
    commissions.appel_id,
    rapprochement.statut_rapprochement,
    rapprochement.montant_encaisse_cents
from {{ ref('stg_commissions') }} as commissions
join {{ ref('int_commissions_attendues') }} as attendues on attendues.appel_id = commissions.appel_id
join {{ ref('int_rapprochement_cotisations') }} as rapprochement
  on rapprochement.appel_id = commissions.appel_id
where attendues.assiette = 'cotisation_encaissee'
  and attendues.encaissement_est_delegue
  and rapprochement.montant_encaisse_cents <= 0
