-- {{ config(severity='warn') }}
-- Severite avertissement. Les ecarts de rapprochement ne sont pas des defauts de la chaine : ce sont
-- des cas de gestion, un trop percu, un acompte, un virement mal adresse. Ils doivent etre comptes et
-- visibles dans la sortie du build, et ils ne doivent pas arreter le graphe.
{{ config(severity='warn') }}
select appel_id, reference_appel, numero_porteur, statut_rapprochement, reste_du_cents
from {{ ref('int_rapprochement_cotisations') }}
where statut_rapprochement = 'ecart'
