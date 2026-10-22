-- Dispersion de la consommation, annee 2025 : contrats des produits a prestations deleguees, en cours aux deux
-- cliches du 31/12/2024 et du 31/12/2025 (une annee pleine de garantie). Le ratio d un contrat est ses
-- prestations reglees de 2025 sur sa cotisation annualisee. Un ratio uniforme serait aussi faux qu un ratio
-- demesure : cette requete montre que la consommation est concentree sur une minorite de contrats.
with annee as (select date '2025-01-01' d0, date '2025-12-31' d1),
pleins as (
  select a.contrat_id, a.branche_id, a.cotisation_annualisee_euros prime
  from analytique_marts.fct_portefeuille_mensuel a
  join analytique_marts.fct_portefeuille_mensuel b on b.contrat_id=a.contrat_id and b.date_cliche = date '2024-12-31'
  join analytique_marts.dim_produit p on p.produit_id=a.produit_id and p.gestion_prestations_deleguee
  where a.date_cliche = date '2025-12-31' and a.statut_contrat='en_cours' and b.statut_contrat='en_cours'),
conso as (
  select contrat_id, sum(rembourse_euros) r from analytique_marts.fct_prestations, annee
  where statut_prestation='reglee' and date_reglement between d0 and d1 group by 1),
x as (select p.contrat_id, p.prime, coalesce(c.r,0) r, coalesce(c.r,0)/p.prime ratio from pleins p left join conso c using (contrat_id))
select count(*) contrats,
  round(100.0*count(*) filter (where r=0)/count(*),1) as pct_sans_prestation,
  round((percentile_cont(0.5) within group (order by ratio))::numeric*100,0) mediane_pct,
  round((percentile_cont(0.75) within group (order by ratio))::numeric*100,0) p75_pct,
  round((percentile_cont(0.9) within group (order by ratio))::numeric*100,0) p90_pct,
  round((percentile_cont(0.99) within group (order by ratio))::numeric*100,0) p99_pct,
  round(100.0*sum(r) filter (where ratio >= (select percentile_cont(0.9) within group (order by ratio) from x))/sum(r),1) as part_des_10pct_les_plus_consommateurs,
  round(100*sum(r)/sum(prime),1) as ratio_global_pct
from x;
