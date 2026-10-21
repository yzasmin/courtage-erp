-- Chaque appel de cotisation avec son porteur, son produit, sa compagnie et son apporteur.
--
-- Le porteur est un contrat en individuel et une police en collectif. La colonne `numero_porteur`
-- reunit les deux, parce que tout ce qui suit, rapprochement, commission, bordereau, raisonne sur le
-- porteur et non sur sa forme juridique.
--
-- L'apporteur retenu est celui en vigueur **a la date d'echeance**, reconstitue par le dernier avenant
-- pris effet a cette date en individuel, et porte par la police en collectif. Prendre l'apporteur
-- courant du contrat reecrirait l'histoire des bordereaux deja regles a chaque changement d'apporteur.

with appels as (
    select * from {{ ref('stg_appels_cotisation') }}
),

avenant_en_vigueur as (
    select
        appels.appel_id,
        avenants.apporteur_id,
        row_number() over (
            partition by appels.appel_id
            order by avenants.date_effet desc, avenants.numero_ordre desc
        ) as rang
    from appels
    join {{ ref('stg_avenants') }} as avenants
      on avenants.contrat_id = appels.contrat_id
     and avenants.date_effet <= appels.date_echeance
    where appels.contrat_id is not null
)

select
    appels.appel_id,
    appels.reference_appel,
    appels.est_un_appel_groupe,
    appels.contrat_id,
    appels.police_id,
    coalesce(contrats.numero_contrat, polices.numero_police) as numero_porteur,
    coalesce(contrats.produit_id, polices.produit_id)        as produit_id,
    produits.code_produit,
    produits.compagnie_id,
    produits.branche_id,
    coalesce(avenant_en_vigueur.apporteur_id, polices.apporteur_id) as apporteur_id,
    coalesce(contrats.date_effet, polices.date_effet)               as date_effet_porteur,
    coalesce(contrats.date_resiliation, polices.date_resiliation)   as date_resiliation_porteur,
    appels.nombre_affilies,
    appels.periode_debut,
    appels.periode_fin,
    appels.date_echeance,
    appels.mois_echeance,
    appels.montant_ht_cents,
    appels.montant_taxe_cents,
    appels.montant_total_cents,
    appels.taux_taxe_bp,
    appels.statut_appel
from appels
left join {{ ref('stg_contrats') }} as contrats on contrats.contrat_id = appels.contrat_id
left join {{ ref('stg_polices') }}  as polices  on polices.police_id   = appels.police_id
left join avenant_en_vigueur on avenant_en_vigueur.appel_id = appels.appel_id and avenant_en_vigueur.rang = 1
join {{ ref('stg_produits') }} as produits
  on produits.produit_id = coalesce(contrats.produit_id, polices.produit_id)
