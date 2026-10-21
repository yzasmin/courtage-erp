-- Recalcule, en SQL, la commission attendue pour chaque appel, a partir des baremes dates.
--
-- Ce modele existe pour une seule raison : **controler le calcul applicatif**. Les commissions sont
-- calculees par la chaine Python, qui lit les memes baremes. Les recalculer ici par un chemin
-- independant, puis comparer, est la seule facon de detecter une erreur de calcul sans la reproduire.
-- Un test de severite erreur compare les deux et echoue au-dela d'un centime d'ecart.
--
-- L'arrondi reproduit celui du code applicatif : au centime le plus proche, demie vers le haut. En
-- PostgreSQL, `round(numeric, 0)` arrondit ainsi.

with taux as (
    select
        appels.appel_id,
        appels.produit_id,
        appels.date_echeance,
        taux_commission.taux_bp,
        taux_commission.assiette,
        row_number() over (
            partition by appels.appel_id
            order by taux_commission.date_debut_validite desc
        ) as rang
    from {{ ref('int_appels_enrichis') }} as appels
    join {{ ref('stg_taux_commission') }} as taux_commission
      on taux_commission.produit_id = appels.produit_id
     and taux_commission.date_debut_validite <= appels.date_echeance
     and (taux_commission.date_fin_validite is null or taux_commission.date_fin_validite >= appels.date_echeance)
),

base as (
    select
        rapprochement.appel_id,
        rapprochement.reference_appel,
        rapprochement.produit_id,
        rapprochement.compagnie_id,
        rapprochement.apporteur_id,
        rapprochement.mois_echeance,
        rapprochement.montant_appele_cents,
        rapprochement.montant_appele_ht_cents,
        least(rapprochement.montant_encaisse_cents, rapprochement.montant_appele_cents) as encaisse_retenu_cents,
        taux.taux_bp,
        taux.assiette
    from {{ ref('int_rapprochement_cotisations') }} as rapprochement
    join taux on taux.appel_id = rapprochement.appel_id and taux.rang = 1
),

assiette_calculee as (
    select
        base.*,
        case
            when assiette = 'cotisation_appelee' then montant_appele_ht_cents
            when encaisse_retenu_cents <= 0 then 0
            when encaisse_retenu_cents >= montant_appele_cents then montant_appele_ht_cents
            else round(
                encaisse_retenu_cents::numeric * montant_appele_ht_cents::numeric
                / nullif(montant_appele_cents, 0)::numeric,
                0
            )::bigint
        end as assiette_attendue_cents
    from base
)

select
    appel_id,
    reference_appel,
    produit_id,
    compagnie_id,
    apporteur_id,
    mois_echeance,
    assiette,
    taux_bp,
    assiette_attendue_cents,
    round(assiette_attendue_cents::numeric * taux_bp::numeric / 10000, 0)::bigint as commission_attendue_cents
from assiette_calculee
