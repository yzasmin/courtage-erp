-- Les pieges de l'indicateur 4, au 30/09/2026.
select
    -- reference : cliche du 30/09/2026
    (select count(*) from analytique_marts.fct_portefeuille_mensuel
      where date_cliche = date '2026-09-30')                                                 as reference_contrats,
    -- verification croisee : statut courant du contrat (en cours ou suspendu)
    (select count(*) from public.contrat where statut in ('en_cours', 'suspendu'))           as statut_courant_contrats,
    -- piege 1 : compter les devis comme des contrats
    (select count(*) from public.contrat where statut <> 'resilie')                          as avec_devis_contrats,
    -- piege 2 : additionner les cliches de l'annee 2025 au lieu de lire une date
    (select count(*) from analytique_marts.fct_portefeuille_mensuel
      where date_cliche between date '2025-01-01' and date '2025-12-31')                     as somme_des_12_cliches_2025,
    -- piege 3 : la cotisation courante des contrats en cours plutot que celle du cliche
    round((select sum(cotisation_annualisee_euros) from analytique_marts.fct_portefeuille_mensuel
            where date_cliche = date '2026-09-30'), 2)                                       as annualisee_reference_euros,
    round((select sum(c.cotisation_mensuelle_cents * 12) from public.contrat c
            where c.statut = 'en_cours') / 100.0, 2)                                         as annualisee_statut_courant_euros,
    -- piege 4 : inclure les suspendus dans la cotisation annualisee
    round((select sum(cotisation_mensuelle_euros * 12) from analytique_marts.fct_portefeuille_mensuel
            where date_cliche = date '2026-09-30'), 2)                                       as annualisee_suspendus_inclus_euros;
