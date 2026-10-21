-- Tableau de la qualite des flux recus, mois par mois et flux par flux.
--
-- C'est l'etat que le responsable de gestion regarde : combien de bordereaux recus, combien rejetes,
-- pour quelles causes, et quelle part du courrier du mois a pu etre traitee.

select
    periode,
    to_char(periode, 'YYYY-MM')                                          as annee_mois,
    type_flux,
    count(*)                                                             as lots_recus,
    sum(case when est_rejete then 1 else 0 end)                          as lots_rejetes,
    sum(case when statut_lot = 'charge' then 1 else 0 end)               as lots_charges,
    sum(nombre_lignes_fichier)                                           as lignes_recues,
    sum(lignes_en_base)                                                  as lignes_chargees,
    sum(anomalies_bloquantes)                                            as anomalies_bloquantes,
    sum(avertissements)                                                  as avertissements,
    bool_and(rejet_sans_ecriture_partielle)                              as rejet_integral_respecte,
    round(
        100.0 * sum(lignes_en_base) / nullif(sum(nombre_lignes_fichier), 0), 1
    )                                                                    as part_lignes_chargees_pourcent
from {{ ref('int_qualite_lots') }}
group by periode, type_flux
