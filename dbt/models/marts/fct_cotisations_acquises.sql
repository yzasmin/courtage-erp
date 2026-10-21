-- Fait cotisations acquises : une ligne par appel et par mois couvert.
--
-- Une cotisation **emise** est ce que le cabinet appelle a une echeance. Une cotisation **acquise** est
-- la part de cette cotisation qui correspond au risque effectivement couru pendant la periode : un
-- appel annuel emis en octobre n'est acquis qu'a un douzieme par mois. Comparer des prestations d'une
-- periode a des cotisations emises, c'est comparer des sinistres de trois mois a des primes de douze.
--
-- La repartition est faite au prorata des jours, sur la periode que l'appel couvre reellement
-- (`periode_debut` a `periode_fin`, bornes incluses). Aucune valeur n'est arrondie : l'arrondi par
-- ligne ferait deriver la somme, et un test verifie que la somme des parts egale l'appel.
--
-- La cle `mois_acquisition` est le premier jour du mois, pour se rattacher a `dim_date`. Un appel dont
-- la periode depasse la date d'arret n'est acquis que jusqu'a cette date : le reste n'est pas couru.

with mois as (
    select distinct premier_jour_du_mois, dernier_jour_du_mois
    from {{ ref('dim_date') }}
)

select
    appels.appel_id,
    mois.premier_jour_du_mois                                   as mois_acquisition,
    appels.contrat_id,
    appels.police_id,
    appels.produit_id,
    appels.compagnie_id,
    appels.branche_id,
    appels.apporteur_id,
    (least(appels.periode_fin, mois.dernier_jour_du_mois)
        - greatest(appels.periode_debut, mois.premier_jour_du_mois) + 1)  as jours_acquis,
    (appels.periode_fin - appels.periode_debut + 1)             as jours_de_la_periode,
    (appels.montant_ht_cents / 100.0)
        * (least(appels.periode_fin, mois.dernier_jour_du_mois)
            - greatest(appels.periode_debut, mois.premier_jour_du_mois) + 1)
        / (appels.periode_fin - appels.periode_debut + 1)       as cotisation_acquise_ht_euros
from {{ ref('int_appels_enrichis') }} as appels
join mois
  on appels.periode_debut <= mois.dernier_jour_du_mois
 and appels.periode_fin >= mois.premier_jour_du_mois
