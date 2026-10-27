-- Variables de la prediction de resiliation (module 5), une ligne par contrat au portefeuille et par
-- date d'observation.
--
-- La regle qui fait la valeur de ce modele : **rien de posterieur a la date d'observation**. Chaque
-- variable est lue sur les seuls avenants dont la date d'effet est anterieure ou egale a cette date. La
-- date de saisie d'un avenant est egale a sa date d'effet dans ce portefeuille, donc filtrer sur l'une
-- revient a filtrer sur l'autre ; le test `ml_aucune_information_posterieure` le reverifie.
--
-- Les dates d'observation sont tous les 1er du mois, de janvier 2021 a la date d'arret de l'historique.
-- Le 1er janvier, jour de l'echeance et de la revalorisation, sert a l'apprentissage ; le dernier 1er
-- du mois sert au scoring mensuel. La cible n'est renseignee que si sa fenetre de douze mois est
-- entierement observee : sinon elle vaut null, et la ligne ne peut servir qu'au scoring.
--
-- La sinistralite n'est pas une variable : l'historique des prestations commence le 1er octobre 2023,
-- elle n'est donc pas calculable aux dates d'apprentissage. Voir docs/DECISIONS.md.

with arret as (
    select max(date_jour) as date_arret from {{ ref('dim_date') }}
),

dates_observation as (
    select generate_series(
        date '2021-01-01',
        (select date_arret from arret),
        interval '1 month'
    )::date as date_observation
),

avenants as (
    select
        avenants.*,
        lag(avenants.cotisation_mensuelle_cents) over (
            partition by avenants.contrat_id order by avenants.numero_ordre
        ) as cotisation_precedente_cents
    from {{ ref('stg_avenants') }} as avenants
    where avenants.numero_ordre >= 1
),

-- Version du contrat en vigueur a la date d'observation : le dernier avenant d'effet anterieur ou egal.
version_a_date as (
    select distinct on (avenants.contrat_id, dates.date_observation)
        dates.date_observation,
        avenants.contrat_id,
        avenants.statut_apres_avenant as statut_contrat,
        avenants.apporteur_id,
        avenants.cotisation_mensuelle_cents
    from dates_observation as dates
    join avenants on avenants.date_effet <= dates.date_observation
    order by avenants.contrat_id, dates.date_observation, avenants.numero_ordre desc
),

historique_a_date as (
    select
        dates.date_observation,
        avenants.contrat_id,
        count(*) filter (where avenants.type_avenant = 'suspension')          as nb_suspensions,
        count(*) filter (where avenants.type_avenant = 'changement_formule')  as nb_changements_formule,
        max(avenants.date_effet)                                              as dernier_avenant_lu
    from dates_observation as dates
    join avenants on avenants.date_effet <= dates.date_observation
    group by dates.date_observation, avenants.contrat_id
),

-- Derniere revalorisation connue dans les douze mois precedant l'observation, en points de base.
revalorisation_a_date as (
    select distinct on (avenants.contrat_id, dates.date_observation)
        dates.date_observation,
        avenants.contrat_id,
        round(
            10000.0 * (avenants.cotisation_mensuelle_cents - avenants.cotisation_precedente_cents)
            / nullif(avenants.cotisation_precedente_cents, 0)
        )::int as revalorisation_bp
    from dates_observation as dates
    join avenants
        on avenants.type_avenant = 'revalorisation_tarifaire'
        and avenants.date_effet <= dates.date_observation
        and avenants.date_effet > dates.date_observation - interval '12 months'
    order by avenants.contrat_id, dates.date_observation, avenants.date_effet desc
),

-- Une seule resiliation par contrat, puisque le statut resilie est terminal : une jointure par contrat
-- remplace la sous-requete correlee de la premiere version, executee pour chacune des 180 000 lignes.
resiliations as (
    select contrat_id, min(date_effet) as date_resiliation
    from avenants
    where type_avenant = 'resiliation'
    group by contrat_id
)

select
    version.date_observation,
    contrats.contrat_id,
    contrats.numero_contrat,
    contrats.adherent_id,
    produits.code_produit,
    produits.code_branche,
    apporteurs.code_apporteur,
    contrats.est_une_affiliation,
    version.statut_contrat = 'suspendu'                                       as est_suspendu,
    extract(year from age(version.date_observation, adherents.date_naissance))::int as age,
    (
        extract(year from age(version.date_observation, contrats.date_effet)) * 12
        + extract(month from age(version.date_observation, contrats.date_effet))
    )::int                                                                    as anciennete_mois,
    version.cotisation_mensuelle_cents,
    coalesce(revalorisation.revalorisation_bp, 0)                             as revalorisation_bp,
    historique.nb_suspensions,
    historique.nb_changements_formule,
    historique.dernier_avenant_lu,
    -- Cible : une resiliation prend effet dans les douze mois, bornes comprises. Une resiliation a
    -- l'echeance decidee au 1er janvier prend effet au 1er janvier suivant, d'ou la borne incluse.
    case
        when version.date_observation + interval '12 months' > (select date_arret from arret) then null
        when resiliations.date_resiliation > version.date_observation
            and resiliations.date_resiliation <= version.date_observation + interval '12 months' then 1
        else 0
    end                                                                       as resilie_12_mois
from version_a_date as version
join {{ ref('stg_contrats') }} as contrats on contrats.contrat_id = version.contrat_id
join {{ ref('stg_adherents') }} as adherents on adherents.adherent_id = contrats.adherent_id
join {{ ref('dim_produit') }} as produits on produits.produit_id = contrats.produit_id
join {{ ref('dim_apporteur') }} as apporteurs on apporteurs.apporteur_id = version.apporteur_id
join historique_a_date as historique
    on historique.contrat_id = version.contrat_id
    and historique.date_observation = version.date_observation
left join revalorisation_a_date as revalorisation
    on revalorisation.contrat_id = version.contrat_id
    and revalorisation.date_observation = version.date_observation
left join resiliations on resiliations.contrat_id = version.contrat_id
where version.statut_contrat in ('en_cours', 'suspendu')
