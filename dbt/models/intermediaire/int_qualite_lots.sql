-- Qualite de chaque lot recu : verdict, anomalies par severite, et respect du rejet integral.
--
-- La colonne `rejet_sans_ecriture_partielle` est le controle le plus important du module : un lot
-- rejete ne doit avoir charge aucune ligne. Elle est verifiee ici en relisant la couche brute, et non
-- en relisant le compteur du journal : un compteur peut mentir, une jointure sur les lignes reellement
-- presentes ne peut pas.

with lignes_brutes as (
    select lot_id, count(*) as lignes from {{ ref('stg_brut_cotisations') }} group by lot_id
    union all
    select lot_id, count(*) as lignes from {{ ref('stg_brut_encaissements') }} group by lot_id
    union all
    select lot_id, count(*) as lignes from {{ ref('stg_brut_prestations') }} group by lot_id
),

presentes as (
    select lot_id, sum(lignes) as lignes_en_base from lignes_brutes group by lot_id
),

anomalies as (
    select
        lot_id,
        count(*)                                        as anomalies_total,
        sum(case when est_bloquante then 1 else 0 end)  as anomalies_bloquantes,
        sum(case when est_bloquante then 0 else 1 end)  as avertissements,
        count(distinct code_anomalie)                   as codes_distincts
    from {{ ref('stg_anomalies_lot') }}
    group by lot_id
)

select
    lots.lot_id,
    lots.reference_lot,
    lots.nom_fichier,
    lots.type_flux,
    lots.format_fichier,
    lots.periode,
    lots.sha256,
    lots.statut_lot,
    lots.est_rejete,
    lots.motif_rejet,
    lots.nombre_lignes_fichier,
    lots.nombre_lignes_chargees,
    coalesce(presentes.lignes_en_base, 0)         as lignes_en_base,
    coalesce(anomalies.anomalies_total, 0)        as anomalies_total,
    coalesce(anomalies.anomalies_bloquantes, 0)   as anomalies_bloquantes,
    coalesce(anomalies.avertissements, 0)         as avertissements,
    coalesce(anomalies.codes_distincts, 0)        as codes_distincts,
    lots.montant_total_declare_cents,
    lots.montant_total_calcule_cents,
    (not lots.est_rejete) or coalesce(presentes.lignes_en_base, 0) = 0
        as rejet_sans_ecriture_partielle,
    lots.nombre_lignes_chargees = coalesce(presentes.lignes_en_base, 0)
        as compteur_conforme_aux_lignes
from {{ ref('stg_lots_recus') }} as lots
left join presentes  on presentes.lot_id  = lots.lot_id
left join anomalies  on anomalies.lot_id  = lots.lot_id
