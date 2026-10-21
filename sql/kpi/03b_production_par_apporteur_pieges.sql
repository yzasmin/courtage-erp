-- Les pieges de l'indicateur 3, sur l'annee 2025 : ce que donneraient l'apporteur et la cotisation COURANTS
-- du contrat, et le comptage des remises en vigueur comme des affaires nouvelles.
with periode as (select date '2025-01-01' as debut, date '2025-12-31' as fin),
reference as (
    select m.contrat_id, m.apporteur_id, m.cotisation_annualisee_cents
    from analytique_marts.fct_mouvements_portefeuille m, periode p
    where m.type_mouvement = 'affaire_nouvelle' and m.date_mouvement between p.debut and p.fin
),
courant as (
    select r.contrat_id,
           c.apporteur_id as apporteur_courant,
           c.cotisation_mensuelle_cents * 12 as annualisee_courante_cents,
           r.apporteur_id as apporteur_a_la_mise_en_vigueur,
           r.cotisation_annualisee_cents
    from reference r join public.contrat c on c.id = r.contrat_id
)
select
    (select count(*) from reference)                                                           as affaires_nouvelles_2025,
    (select count(*) from courant where apporteur_courant <> apporteur_a_la_mise_en_vigueur)   as contrats_dont_l_apporteur_a_change,
    round((select sum(cotisation_annualisee_cents) from courant) / 100.0, 2)                   as annualisee_a_la_mise_en_vigueur_euros,
    round((select sum(annualisee_courante_cents) from courant) / 100.0, 2)                     as annualisee_courante_euros,
    (select count(*) from public.avenant a, periode p
      where a.type_avenant in ('mise_en_vigueur', 'remise_en_vigueur')
        and a.date_effet between p.debut and p.fin)                                            as mises_et_remises_en_vigueur,
    (select count(*) from public.avenant a, periode p
      where a.type_avenant = 'remise_en_vigueur'
        and a.date_effet between p.debut and p.fin)                                            as dont_remises_en_vigueur;
