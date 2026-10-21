-- Produit, sa branche et sa compagnie en une seule dimension : c'est ainsi que le metier le lit.
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
    produits.date_fermeture
from {{ ref('stg_produits') }} as produits
join {{ ref('stg_branches') }} as branches on branches.branche_id = produits.branche_id
join {{ ref('stg_compagnies') }} as compagnies on compagnies.compagnie_id = produits.compagnie_id
