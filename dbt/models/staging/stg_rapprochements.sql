-- Verdict du rapprochement, mouvement par mouvement, avec la methode employee.
select
    id                      as rapprochement_id,
    lot_id,
    encaissement_id,
    reference_bancaire,
    appel_id,
    methode,
    statut                  as statut_rapprochement,
    montant_encaisse_cents,
    montant_appele_cents,
    ecart_cents,
    fenetre_jours,
    statut in ('rapproche', 'partiel') as est_abouti
from {{ source('fichiers_recus', 'rapprochement_ligne') }}
