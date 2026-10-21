-- Severite avertissement. Consommation annuelle qui atteint quatre-vingt-cinq pour cent du plafond de
-- la garantie. Information de gestion : l'adherent approche de sa limite.
--
-- Restreint aux mois couverts par les lots reellement charges, et c'est important. Sans cette
-- restriction, le test remonte toute la consommation des trois annees d'historique, soit onze mille
-- lignes mesurees au premier essai, et un avertissement de onze mille lignes n'est pas lu. Le test
-- porte donc sur le courrier que la chaine vient de traiter.
{{ config(severity='warn') }}

with periodes_traitees as (
    select distinct periode from {{ ref('stg_lots_recus') }} where statut_lot = 'charge'
),

cumul as (
    select
        prestations.contrat_id,
        prestations.garantie_id,
        prestations.annee_soins,
        max(prestations.plafond_annuel_cents)    as plafond_annuel_cents,
        sum(prestations.montant_rembourse_cents) as consomme_cents
    from {{ ref('fct_prestations') }} as prestations
    where prestations.plafond_annuel_cents is not null
      and prestations.statut_prestation = 'reglee'
      and prestations.mois_soins in (select periode from periodes_traitees)
    group by prestations.contrat_id, prestations.garantie_id, prestations.annee_soins
)

select contrat_id, garantie_id, annee_soins, consomme_cents, plafond_annuel_cents
from cumul
where consomme_cents >= plafond_annuel_cents * 0.85
