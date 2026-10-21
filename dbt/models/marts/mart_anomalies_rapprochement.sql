-- Les ecarts de rapprochement, tels que l'ecran des anomalies de l'ERP les affiche.
--
-- Un seul endroit definit ce qui est une anomalie de rapprochement, et l'interface comme le tableau de
-- bord le lisent ici. Deux definitions, une par ecran, finiraient par divergier.

select
    rapprochement.appel_id,
    rapprochement.reference_appel,
    rapprochement.numero_porteur,
    rapprochement.compagnie_id,
    rapprochement.apporteur_id,
    rapprochement.produit_id,
    rapprochement.date_echeance,
    rapprochement.mois_echeance,
    rapprochement.statut_rapprochement,
    rapprochement.methode_retenue,
    rapprochement.nombre_mouvements,
    (rapprochement.montant_appele_cents / 100.0)::numeric(14, 2)   as appele_euros,
    (rapprochement.montant_encaisse_cents / 100.0)::numeric(14, 2) as encaisse_euros,
    (rapprochement.reste_du_cents / 100.0)::numeric(14, 2)         as reste_du_euros,
    rapprochement.reste_du_cents
from {{ ref('int_rapprochement_cotisations') }} as rapprochement
where rapprochement.statut_rapprochement <> 'rapproche'
