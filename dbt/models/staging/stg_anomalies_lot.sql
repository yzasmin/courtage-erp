-- Rapport d'anomalies, conserve meme quand le lot est rejete : c'est la piece renvoyee a l'emetteur.
select
    id              as anomalie_id,
    lot_id,
    ligne_numero,
    reference_ligne,
    code            as code_anomalie,
    severite,
    message,
    valeur_constatee,
    valeur_attendue,
    severite = 'bloquant' as est_bloquante
from {{ source('fichiers_recus', 'anomalie_lot') }}
