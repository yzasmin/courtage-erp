-- Severite erreur. Le nombre de lignes annonce par le journal doit egaler le nombre de lignes
-- reellement en couche brute. Un journal qui annonce plus que ce qu'il contient est pire qu'un journal
-- absent : il donne confiance a tort.
select
    lot_id,
    reference_lot,
    nombre_lignes_chargees,
    lignes_en_base
from {{ ref('int_qualite_lots') }}
where not compteur_conforme_aux_lignes
