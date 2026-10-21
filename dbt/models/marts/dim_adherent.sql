-- Adherent : la personne couverte, avec ce dont le pilotage a besoin pour decouper les indicateurs.
--
-- Ni nom ni prenom ni coordonnees : un tableau de bord n'a aucune raison de les porter, et c'est une
-- donnee personnelle de moins a proteger dans un fichier que l'on ouvre sur un poste.
--
-- L'age est celui a la date d'arret de l'historique. Un age change avec le temps : pour decouper des
-- mouvements, la tranche d'age **au moment du mouvement** est portee par `fct_mouvements_portefeuille`.

with arret as (
    select max(date_jour) as date_arret from {{ ref('dim_date') }}
)

select
    adherents.adherent_id,
    adherents.numero_adherent,
    adherents.sexe,
    adherents.departement,
    adherents.entreprise_id,
    case when adherents.entreprise_id is null then 'individuel' else 'collectif' end as type_couverture,
    extract(year from age(arret.date_arret, adherents.date_naissance))::int          as age_a_la_date_d_arret,
    {{ tranche_age("extract(year from age(arret.date_arret, adherents.date_naissance))") }} as tranche_age
from {{ ref('stg_adherents') }} as adherents
cross join arret
