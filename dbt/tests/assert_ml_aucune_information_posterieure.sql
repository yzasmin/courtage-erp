-- Garde-fou contre la fuite d'information : aucune variable ne doit avoir lu un avenant d'effet ou de
-- saisie posterieur a la date d'observation. Une seule ligne renvoyee suffit a invalider l'apprentissage.
select variables.date_observation, variables.contrat_id
from {{ ref('ml_variables_resiliation') }} as variables
where variables.dernier_avenant_lu > variables.date_observation
   or exists (
        select 1
        from {{ ref('stg_avenants') }} as avenants
        where avenants.contrat_id = variables.contrat_id
            and avenants.date_effet <= variables.date_observation
            and avenants.date_saisie::date > variables.date_observation
   )
