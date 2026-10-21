-- Mouvements bancaires qu'aucun appel ne reclame. Un credit que personne ne sait rattacher est un
-- probleme de tresorerie, pas une ligne a oublier.
select
    rapprochements.rapprochement_id,
    rapprochements.reference_bancaire,
    rapprochements.lot_id,
    lots.nom_fichier,
    lots.periode,
    rapprochements.methode,
    rapprochements.statut_rapprochement,
    (rapprochements.montant_encaisse_cents / 100.0)::numeric(14, 2) as montant_euros,
    rapprochements.montant_encaisse_cents
from {{ ref('stg_rapprochements') }} as rapprochements
join {{ ref('stg_lots_recus') }} as lots on lots.lot_id = rapprochements.lot_id
where rapprochements.statut_rapprochement = 'non_trouve'
