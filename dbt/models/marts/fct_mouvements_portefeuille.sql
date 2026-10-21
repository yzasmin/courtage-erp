-- Fait mouvements de portefeuille : une ligne par entree (affaire nouvelle) ou sortie (resiliation).
--
-- Une affaire nouvelle est la mise en vigueur d'un contrat. Ni une remise en vigueur apres suspension,
-- ni un changement d'apporteur, ni une revalorisation : ce sont des avenants, pas de la production.
-- Un devis jamais transforme n'est pas une affaire, il n'est donc pas ici.
--
-- L'apporteur et la cotisation sont ceux de **la version du contrat au jour du mouvement**, pas ceux du
-- contrat courant. Le contrat courant a pu changer d'apporteur ou etre revalorise depuis : crediter la
-- production de 2024 a l'apporteur de 2026, ou la cotisation de 2026, reecrit l'histoire.
--
-- La cotisation annualisee est la cotisation mensuelle hors taxe multipliee par douze. Ce n'est pas ce
-- qui a ete appele dans la periode, qui depend du fractionnement et du jour d'effet.

with mouvements as (
    select
        versions.contrat_id,
        versions.numero_contrat,
        versions.adherent_id,
        versions.produit_id,
        versions.apporteur_id,
        versions.valide_du                                   as date_mouvement,
        versions.date_effet_contrat,
        versions.est_une_affiliation,
        versions.motif_resiliation,
        versions.cotisation_mensuelle_cents,
        case versions.type_avenant
            when 'mise_en_vigueur' then 'affaire_nouvelle'
            when 'resiliation'     then 'resiliation'
        end                                                  as type_mouvement
    from {{ ref('int_contrat_versions') }} as versions
    where versions.type_avenant in ('mise_en_vigueur', 'resiliation')
)

select
    mouvements.contrat_id || '-' || mouvements.type_mouvement                    as mouvement_id,
    mouvements.type_mouvement,
    mouvements.contrat_id,
    mouvements.numero_contrat,
    mouvements.adherent_id,
    mouvements.produit_id,
    produits.compagnie_id,
    produits.branche_id,
    mouvements.apporteur_id,
    mouvements.date_mouvement,
    mouvements.date_effet_contrat,
    mouvements.est_une_affiliation,
    mouvements.motif_resiliation,
    (extract(year from age(mouvements.date_mouvement, adherents.date_naissance)))::int as age_au_mouvement,
    {{ tranche_age("extract(year from age(mouvements.date_mouvement, adherents.date_naissance))") }}
                                                                                 as tranche_age_au_mouvement,
    (extract(year from age(mouvements.date_mouvement, mouvements.date_effet_contrat)) * 12
        + extract(month from age(mouvements.date_mouvement, mouvements.date_effet_contrat)))::int
                                                                                 as anciennete_en_mois,
    (mouvements.cotisation_mensuelle_cents * 12 / 100.0)::numeric(14, 2)         as cotisation_annualisee_euros,
    mouvements.cotisation_mensuelle_cents * 12                                   as cotisation_annualisee_cents
from mouvements
join {{ ref('stg_produits') }} as produits on produits.produit_id = mouvements.produit_id
join {{ ref('stg_adherents') }} as adherents on adherents.adherent_id = mouvements.adherent_id
