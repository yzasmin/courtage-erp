-- Confronte le bordereau de la compagnie au quittancement du cabinet, ligne par ligne.
--
-- C'est le controle que la delegation de gestion rend necessaire : le cabinet quittance au nom de la
-- compagnie, la compagnie envoie son propre etat, et les deux doivent dire la meme chose. Un ecart
-- signifie qu'un des deux a tort, et le gestionnaire doit savoir lequel avant de commissionner.

with recues as (
    select
        brut.reference_appel,
        brut.lot_id,
        brut.numero_contrat,
        brut.numero_police,
        brut.montant_ht_cents    as montant_ht_declare_cents,
        brut.montant_total_cents as montant_total_declare_cents,
        brut.periode_debut       as periode_debut_declaree,
        brut.date_echeance       as date_echeance_declaree
    from {{ ref('stg_brut_cotisations') }} as brut
    join {{ ref('stg_lots_recus') }} as lots on lots.lot_id = brut.lot_id
    where lots.statut_lot = 'charge'
)

select
    recues.reference_appel,
    recues.lot_id,
    appels.appel_id,
    appels.numero_porteur,
    appels.compagnie_id,
    appels.mois_echeance,
    recues.montant_total_declare_cents,
    appels.montant_total_cents                                       as montant_total_appele_cents,
    recues.montant_total_declare_cents - appels.montant_total_cents  as ecart_cents,
    recues.date_echeance_declaree,
    appels.date_echeance,
    appels.appel_id is null                                          as absent_du_quittancement,
    case
        when appels.appel_id is null then 'appel_inconnu'
        when recues.montant_total_declare_cents = appels.montant_total_cents then 'conforme'
        else 'ecart_de_montant'
    end as verdict
from recues
left join {{ ref('int_appels_enrichis') }} as appels
  on appels.reference_appel = recues.reference_appel
