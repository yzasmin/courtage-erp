-- Indicateur 4 : portefeuille par branche, a une date (stock).
--   contrats au portefeuille : en cours et suspendus, au dernier jour du mois de la date
--   cotisation annualisee    : cotisation mensuelle hors taxe des seuls contrats en cours, multipliee par douze
with dates(date_cliche) as (
    values (date '2023-12-31'), (date '2024-12-31'), (date '2025-12-31'), (date '2026-09-30')
)
select
    d.date_cliche,
    branches.code_branche,
    branches.libelle_branche,
    count(*)                                              as contrats_au_portefeuille,
    count(*) filter (where f.statut_contrat = 'suspendu') as dont_suspendus,
    round(sum(f.cotisation_annualisee_euros), 2)          as cotisation_annualisee_euros
from dates d
join analytique_marts.fct_portefeuille_mensuel f on f.date_cliche = d.date_cliche
join analytique_marts.dim_branche branches on branches.branche_id = f.branche_id
group by d.date_cliche, branches.code_branche, branches.libelle_branche
order by d.date_cliche, branches.code_branche;
