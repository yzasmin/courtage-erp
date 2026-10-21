-- Severite erreur. Un lot rejete ne doit avoir charge aucune ligne, dans aucune des trois tables de la
-- couche brute. C'est l'exigence « aucune ecriture partielle », verifiee ici sur les lignes reellement
-- presentes et non sur le compteur du journal, qui pourrait mentir.
select
    lot_id,
    reference_lot,
    nom_fichier,
    lignes_en_base
from {{ ref('int_qualite_lots') }}
where est_rejete and lignes_en_base > 0
