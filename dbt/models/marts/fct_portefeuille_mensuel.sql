-- Fait portefeuille : une photographie a chaque fin de mois, une ligne par contrat au portefeuille.
--
-- C'est un stock, pas un flux. Il ne s'additionne pas dans le temps : le portefeuille de fin mars et
-- celui de fin avril contiennent en grande partie les memes contrats, et leur somme n'a aucun sens. Un
-- indicateur de stock se lit a **une date** (la fin de la periode, ou la veille de son debut).
--
-- Le cliche du dernier jour du mois M est le portefeuille au premier jour du mois M+1 avant toute
-- operation : c'est l'effectif de **debut de periode** de M+1, le denominateur du taux de resiliation.
--
-- Un contrat suspendu reste au portefeuille. Sa cotisation annualisee n'est en revanche comptee que s'il
-- est en cours : une garantie suspendue ne donne lieu a aucun appel.

with fins_de_mois as (
    select date_jour as date_cliche
    from {{ ref('dim_date') }}
    where est_dernier_jour_du_mois
)

select
    fins_de_mois.date_cliche,
    versions.contrat_id,
    versions.numero_contrat,
    versions.adherent_id,
    versions.produit_id,
    produits.compagnie_id,
    produits.branche_id,
    versions.apporteur_id,
    versions.statut_contrat,
    versions.est_une_affiliation,
    (versions.cotisation_mensuelle_cents / 100.0)::numeric(14, 2)                  as cotisation_mensuelle_euros,
    case when versions.statut_contrat = 'en_cours'
         then (versions.cotisation_mensuelle_cents * 12 / 100.0)::numeric(14, 2)
         else 0::numeric(14, 2) end                                                as cotisation_annualisee_euros
from {{ ref('int_contrat_versions') }} as versions
join {{ ref('stg_produits') }} as produits on produits.produit_id = versions.produit_id
join fins_de_mois
  on versions.valide_du <= fins_de_mois.date_cliche
 and (versions.valide_au_exclu is null or fins_de_mois.date_cliche < versions.valide_au_exclu)
where versions.est_au_portefeuille
