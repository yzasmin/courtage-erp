-- Produit, sa branche et sa compagnie en une seule dimension : c'est ainsi que le metier le lit.
--
-- `gestion_prestations_deleguee` dit si la compagnie a confie au cabinet le reglement des prestations
-- de ce produit, a la date d'arret de l'historique. C'est le perimetre dans lequel un ratio sinistres
-- sur primes a un sens : sur un produit dont les prestations sont reglees par la compagnie, le cabinet
-- voit les cotisations et ne voit aucune prestation, et le ratio tombe a zero sans rien signifier.
with arret as (
    select max(date_jour) as date_arret from {{ ref('dim_date') }}
),

produits_a_prestations_deleguees as (
    select distinct conventions_produit.produit_id
    from {{ ref('stg_conventions_delegation') }} as conventions
    join {{ ref('stg_actes_delegues') }} as actes
      on actes.convention_id = conventions.convention_id and actes.acte = 'gestion_prestations'
    join {{ ref('stg_conventions_produit') }} as conventions_produit
      on conventions_produit.convention_id = conventions.convention_id
    cross join arret
    where conventions.date_debut_validite <= arret.date_arret
      and (conventions.date_fin_validite is null or conventions.date_fin_validite >= arret.date_arret)
)

select
    produits.produit_id,
    produits.code_produit,
    produits.libelle_produit,
    produits.branche_id,
    branches.code_branche,
    branches.libelle_branche,
    branches.famille_branche,
    produits.compagnie_id,
    compagnies.code_compagnie,
    compagnies.raison_sociale,
    produits.date_ouverture,
    produits.date_fermeture,
    delegues.produit_id is not null as gestion_prestations_deleguee
from {{ ref('stg_produits') }} as produits
join {{ ref('stg_branches') }} as branches on branches.branche_id = produits.branche_id
join {{ ref('stg_compagnies') }} as compagnies on compagnies.compagnie_id = produits.compagnie_id
left join produits_a_prestations_deleguees as delegues on delegues.produit_id = produits.produit_id
