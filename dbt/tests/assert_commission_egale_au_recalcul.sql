-- Severite erreur. La commission calculee par la chaine Python doit egaler celle recalculee en SQL
-- depuis les memes baremes dates. Deux chemins de calcul independants qui divergent signalent une
-- erreur dans l'un des deux, et c'est le seul moyen de la trouver sans la reproduire.
select
    commissions.commission_id,
    commissions.appel_id,
    commissions.assiette_cents                 as assiette_appliquee,
    attendues.assiette_attendue_cents          as assiette_attendue,
    commissions.montant_cents                  as commission_appliquee,
    attendues.commission_attendue_cents        as commission_attendue
from {{ ref('stg_commissions') }} as commissions
join {{ ref('int_commissions_attendues') }} as attendues on attendues.appel_id = commissions.appel_id
where commissions.montant_cents <> attendues.commission_attendue_cents
   or commissions.assiette_cents <> attendues.assiette_attendue_cents
