-- Fait cotisations : une ligne par appel de cotisation, avec son etat de rapprochement.
--
-- Les montants sont exposes en euros, et c'est le seul endroit du projet ou la conversion a lieu. En
-- amont, tout est en centimes entiers, parce qu'un bordereau qui ne tombe pas au centime pres est une
-- anomalie comptable.

select
    rapprochement.appel_id,
    rapprochement.reference_appel,
    appels.est_un_appel_groupe,
    appels.numero_porteur,
    appels.contrat_id,
    appels.police_id,
    appels.produit_id,
    appels.compagnie_id,
    appels.branche_id,
    appels.apporteur_id,
    appels.nombre_affilies,
    appels.date_echeance,
    appels.mois_echeance,
    appels.periode_debut,
    appels.periode_fin,
    appels.statut_appel,
    rapprochement.statut_rapprochement,
    rapprochement.methode_retenue,
    rapprochement.nombre_mouvements,
    (appels.montant_ht_cents / 100.0)::numeric(14, 2)                   as cotisation_ht_euros,
    (appels.montant_taxe_cents / 100.0)::numeric(14, 2)                 as taxe_euros,
    (appels.montant_total_cents / 100.0)::numeric(14, 2)                as cotisation_ttc_euros,
    (rapprochement.montant_encaisse_cents / 100.0)::numeric(14, 2)      as encaisse_euros,
    (rapprochement.reste_du_cents / 100.0)::numeric(14, 2)              as reste_du_euros,
    appels.montant_ht_cents,
    appels.montant_total_cents,
    rapprochement.montant_encaisse_cents,
    rapprochement.reste_du_cents
from {{ ref('int_rapprochement_cotisations') }} as rapprochement
join {{ ref('int_appels_enrichis') }} as appels on appels.appel_id = rapprochement.appel_id
