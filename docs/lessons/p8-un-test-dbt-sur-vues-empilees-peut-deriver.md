Ajouter une colonne calculée à un modèle dbt lu par un test a fait passer ce test de 4 secondes à plus de 24 minutes : le planificateur PostgreSQL rejouait toute la chaîne de vues pour chaque ligne.

# Un test sur des vues empilées peut changer de plan sans prévenir

- **Constat.** `assert_commission_sur_cotisation_encaissee_a_un_encaissement` a pris 1 492 secondes au lieu de 3,8 après
  l'ajout du drapeau de délégation dans `int_commissions_attendues` (une vue, jointe à d'autres vues). Rien n'échouait,
  le build était simplement bloqué : la requête était encore active, huit minutes plus tard, dans `pg_stat_activity`.
- **Ce qui n'a pas marché.** Déplacer le calcul dans la CTE qui lit déjà `int_appels_enrichis` (semi-jointure) n'a pas
  suffi : le test restait au-delà de 280 secondes. Le plan dépendait d'un filtre sur une colonne booléenne calculée
  dans une vue à fonction de fenêtre, que PostgreSQL ne peut pas pousser plus bas.
- **Ce qui a marché.** Matérialiser ce seul modèle en table (`config(materialized='table')`) : 51 324 lignes, 4,9 secondes
  de construction, et les deux tests en 2,2 et 2,5 secondes. Le reste de la couche reste en vues.
- **À retenir.** Un test de sévérité erreur sur des vues empilées doit être chronométré, pas seulement vérifié vert. Un
  modèle de quelques dizaines de milliers de lignes que deux tests joignent à d'autres vues mérite d'être une table. Et
  une commande qui dépasse son délai doit être inspectée côté base (`pg_stat_activity`) avant d'être relancée : relancer
  empile des requêtes qui se concurrencent.
