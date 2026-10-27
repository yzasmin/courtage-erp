-- Une seule ligne par contrat et par date d'observation : sinon un contrat compterait double a
-- l'apprentissage et recevrait deux scores le meme mois.
select date_observation, contrat_id, count(*) as nb
from {{ ref('ml_variables_resiliation') }}
group by date_observation, contrat_id
having count(*) > 1
