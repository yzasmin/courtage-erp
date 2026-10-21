-- Le grain du fait portefeuille : un contrat n'apparait qu'une fois par cliche. Deux lignes pour un meme
-- contrat et une meme date doubleraient l'effectif, sans qu'aucun autre test ne le voie.
select contrat_id, date_cliche, count(*) as nombre_de_lignes
from {{ ref('fct_portefeuille_mensuel') }}
group by contrat_id, date_cliche
having count(*) > 1
