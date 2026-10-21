-- Bordereau mensuel de retrocession par apporteur, agrege : ce que l'apporteur verifie en recevant son
-- releve.
--
-- Le modele s'appelait `mart_bordereau_commissions_apporteur`, et c'etait un contresens de vocabulaire.
-- Ce qui part vers un apporteur est une **retrocession**, la part de commission que le cabinet lui
-- reverse ; la commission, elle, vient de la compagnie et va au cabinet. Les deux ne se confondent
-- jamais dans un cabinet de courtage, et le contenu du modele etait d'ailleurs correct : il agregeait
-- bien `stg_retrocessions`. Seul son nom disait le contraire.
--
-- Le detail ligne a ligne est dans le fichier CSV produit par la chaine. Ce mart donne le recapitulatif
-- qu'un tableau de bord affiche, et il sert de controle : son total doit egaler celui du bordereau
-- enregistre en base, ce qu'un test de severite erreur verifie.

with lignes as (
    select
        retrocessions.apporteur_id,
        retrocessions.periode,
        retrocessions.retrocession_id,
        retrocessions.montant_cents,
        retrocessions.assiette_cents,
        retrocessions.bordereau_id,
        appels.branche_id,
        appels.produit_id
    from {{ ref('stg_retrocessions') }} as retrocessions
    join {{ ref('stg_commissions') }} as commissions
      on commissions.commission_id = retrocessions.commission_id
    join {{ ref('int_appels_enrichis') }} as appels on appels.appel_id = commissions.appel_id
)

select
    lignes.apporteur_id,
    apporteurs.code_apporteur,
    apporteurs.nom_apporteur,
    apporteurs.type_apporteur,
    lignes.periode,
    to_char(lignes.periode, 'YYYY-MM')                    as annee_mois,
    count(*)                                              as nombre_lignes,
    count(distinct lignes.produit_id)                     as nombre_produits,
    -- L'assiette d'une retrocession est la commission encaissee par le cabinet sur ces memes lignes.
    (sum(lignes.assiette_cents) / 100.0)::numeric(14, 2)  as commissions_recues_par_le_cabinet_euros,
    (sum(lignes.montant_cents) / 100.0)::numeric(14, 2)   as retrocession_euros,
    sum(lignes.montant_cents)                             as retrocession_cents,
    max(lignes.bordereau_id)                              as bordereau_id
from lignes
join {{ ref('stg_apporteurs') }} as apporteurs on apporteurs.apporteur_id = lignes.apporteur_id
group by lignes.apporteur_id, apporteurs.code_apporteur, apporteurs.nom_apporteur,
         apporteurs.type_apporteur, lignes.periode
