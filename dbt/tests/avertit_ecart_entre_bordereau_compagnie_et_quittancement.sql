-- Severite avertissement. La compagnie et le cabinet n'annoncent pas le meme montant sur une quittance.
-- Ce n'est pas bloquant, le lot est deja charge et controle, mais un gestionnaire doit trancher avant
-- que la commission ne soit versee.
{{ config(severity='warn') }}
select reference_appel, numero_porteur, montant_total_declare_cents, montant_total_appele_cents, ecart_cents
from {{ ref('int_cotisations_recues_vs_appelees') }}
where verdict <> 'conforme'
