-- Indicateur 3 : production par apporteur.
--   affaires nouvelles    : contrats mis en vigueur dans la periode, rattaches a l'apporteur en vigueur le
--                           jour de la mise en vigueur
--   cotisation annualisee : cotisation mensuelle hors taxe a la mise en vigueur, multipliee par douze
with periodes(periode, debut, fin) as (
    values ('2024', date '2024-01-01', date '2024-12-31'),
           ('2025', date '2025-01-01', date '2025-12-31'),
           ('2026 (9 mois)', date '2026-01-01', date '2026-09-30')
)
select
    p.periode,
    apporteurs.code_apporteur,
    apporteurs.nom_apporteur,
    count(*)                                     as affaires_nouvelles,
    round(sum(m.cotisation_annualisee_euros), 2) as cotisation_annualisee_euros
from periodes p
join analytique_marts.fct_mouvements_portefeuille m
  on m.type_mouvement = 'affaire_nouvelle' and m.date_mouvement between p.debut and p.fin
join analytique_marts.dim_apporteur apporteurs on apporteurs.apporteur_id = m.apporteur_id
group by p.periode, p.debut, apporteurs.code_apporteur, apporteurs.nom_apporteur
order by p.debut, cotisation_annualisee_euros desc, apporteurs.code_apporteur;
