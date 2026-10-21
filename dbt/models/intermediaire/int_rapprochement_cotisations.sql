-- Etat du rapprochement appel par appel : appele, encaisse, reste du, et comment il a ete rapproche.
--
-- Un appel peut recevoir plusieurs mouvements, un acompte puis le solde. Les montants sont donc
-- agreges par appel, et la methode retenue pour la ligne est la plus sure des methodes employees :
-- une correspondance par reference l'emporte sur une correspondance par montant et date, parce que la
-- premiere est une certitude et la seconde une presomption.

with rapprochements as (
    select * from {{ ref('stg_rapprochements') }} where appel_id is not null
),

agrege as (
    select
        appel_id,
        sum(montant_encaisse_cents)                                        as montant_encaisse_cents,
        count(*)                                                           as nombre_mouvements,
        min(case methode when 'reference' then 1 when 'montant_date' then 2 else 3 end) as rang_methode,
        max(case when statut_rapprochement = 'ecart' then 1 else 0 end)     as a_un_ecart
    from rapprochements
    group by appel_id
)

select
    appels.appel_id,
    appels.reference_appel,
    appels.numero_porteur,
    appels.produit_id,
    appels.compagnie_id,
    appels.apporteur_id,
    appels.date_echeance,
    appels.mois_echeance,
    appels.montant_total_cents                                  as montant_appele_cents,
    appels.montant_ht_cents                                     as montant_appele_ht_cents,
    coalesce(agrege.montant_encaisse_cents, 0)                  as montant_encaisse_cents,
    appels.montant_total_cents - coalesce(agrege.montant_encaisse_cents, 0) as reste_du_cents,
    coalesce(agrege.nombre_mouvements, 0)                       as nombre_mouvements,
    case agrege.rang_methode when 1 then 'reference' when 2 then 'montant_date' else 'aucune' end
        as methode_retenue,
    case
        when agrege.appel_id is null then 'non_rapproche'
        when agrege.a_un_ecart = 1 then 'ecart'
        when coalesce(agrege.montant_encaisse_cents, 0) = appels.montant_total_cents then 'rapproche'
        when coalesce(agrege.montant_encaisse_cents, 0) > appels.montant_total_cents then 'ecart'
        else 'partiel'
    end as statut_rapprochement
from {{ ref('int_appels_enrichis') }} as appels
left join agrege on agrege.appel_id = appels.appel_id
