-- Journal des fichiers recus. Un lot, un fichier, un verdict.
select
    id                  as lot_id,
    reference_lot,
    nom_fichier,
    type_flux,
    format_fichier,
    sha256,
    taille_octets,
    compagnie_id,
    periode,
    date_depot,
    statut              as statut_lot,
    nombre_lignes_fichier,
    nombre_lignes_chargees,
    montant_total_declare_cents,
    montant_total_calcule_cents,
    motif_rejet,
    statut = 'rejete'   as est_rejete
from {{ source('fichiers_recus', 'lot_fichier') }}
