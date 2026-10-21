-- Fait prestations : un remboursement servi, rattache a son adherent, son contrat et sa garantie.
select
    prestations.prestation_id,
    prestations.reference_prestation,
    prestations.contrat_id,
    prestations.adherent_id,
    prestations.garantie_id,
    garanties.code_garantie,
    garanties.famille_garantie,
    contrats.numero_contrat,
    contrats.produit_id,
    produits.compagnie_id,
    produits.branche_id,
    contrats.apporteur_id,
    adherents.departement,
    prestations.date_soins,
    prestations.mois_soins,
    prestations.annee_soins,
    prestations.date_reglement,
    prestations.statut_prestation,
    plafonds.plafond_annuel_cents,
    (prestations.montant_demande_cents / 100.0)::numeric(14, 2)   as demande_euros,
    (prestations.montant_rembourse_cents / 100.0)::numeric(14, 2) as rembourse_euros,
    prestations.montant_demande_cents,
    prestations.montant_rembourse_cents
from {{ ref('stg_prestations') }} as prestations
join {{ ref('stg_contrats') }} as contrats on contrats.contrat_id = prestations.contrat_id
join {{ ref('stg_produits') }} as produits on produits.produit_id = contrats.produit_id
join {{ ref('stg_garanties') }} as garanties on garanties.garantie_id = prestations.garantie_id
join {{ ref('stg_adherents') }} as adherents on adherents.adherent_id = prestations.adherent_id
left join {{ ref('stg_plafonds_garantie') }} as plafonds
  on plafonds.formule_id = contrats.formule_id and plafonds.garantie_id = prestations.garantie_id
