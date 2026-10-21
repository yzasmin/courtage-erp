-- Les versions successives d'un contrat, une ligne par avenant pris en vigueur.
--
-- Chaque avenant est une photographie complete du contrat (statut, apporteur, cotisation). La version
-- est valable de sa date d'effet jusqu'a la date d'effet de l'avenant suivant, exclue. Le portefeuille
-- a une date se lit donc par une simple jointure sur l'intervalle, sans rejouer l'historique.
--
-- L'avenant de souscription (ordre 0) est le devis : il n'engage personne et n'entre pas au portefeuille.
-- Deux avenants peuvent porter la meme date d'effet (25 cas) : le dernier par numero d'ordre l'emporte,
-- et le premier devient une version d'une duree nulle, que l'intervalle ecarte de lui-meme.

with versions as (
    select
        avenants.contrat_id,
        avenants.numero_ordre,
        avenants.type_avenant,
        avenants.date_effet                              as valide_du,
        lead(avenants.date_effet) over (
            partition by avenants.contrat_id order by avenants.numero_ordre
        )                                                as valide_au_exclu,
        avenants.statut_apres_avenant                    as statut_contrat,
        avenants.formule_id,
        avenants.apporteur_id,
        avenants.cotisation_mensuelle_cents,
        avenants.motif_resiliation
    from {{ ref('stg_avenants') }} as avenants
    where avenants.numero_ordre >= 1
)

select
    versions.*,
    contrats.numero_contrat,
    contrats.adherent_id,
    contrats.produit_id,
    contrats.date_effet                                  as date_effet_contrat,
    contrats.est_une_affiliation,
    -- Un contrat est au portefeuille tant qu'il n'est pas resilie. Un contrat suspendu y reste : sa
    -- garantie est interrompue, pas son lien contractuel, et il peut etre remis en vigueur.
    versions.statut_contrat in ('en_cours', 'suspendu')  as est_au_portefeuille
from versions
join {{ ref('stg_contrats') }} as contrats on contrats.contrat_id = versions.contrat_id
