-- Personne couverte. En collectif, c'est le salarie affilie a la police de son entreprise.
select
    id               as adherent_id,
    numero_adherent,
    nom,
    prenom,
    date_naissance,
    sexe,
    code_postal,
    departement,
    entreprise_id,
    date_creation
from {{ source('coeur_erp', 'adherent') }}
