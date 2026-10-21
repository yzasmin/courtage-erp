Un modèle qui recalcule en SQL une règle de l'application en est une copie : quand la règle change d'un côté, deux tests de contrôle échouent, et rien ne le dit tant que le projet dbt ne tourne pas dans l'intégration continue.

# Le recalcul SQL doit suivre la règle de l'application

- **Ce qui s'est passé.** La décision D24 (quand la compagnie encaisse elle-même, le cabinet est commissionné sur la
  cotisation appelée hors taxe) a été appliquée dans `flux/commissions.py` lors de la reprise du 21/10/2026. Le modèle
  `int_commissions_attendues`, qui recalcule la commission en SQL pour contrôler le code applicatif, ne la connaissait
  pas. Au premier `dbt build` du module 3 sur la base régénérée, `assert_commission_egale_au_recalcul` et
  `assert_commission_sur_cotisation_encaissee_a_un_encaissement` échouaient sur 1 184 appels, le chiffre exact des
  appels « assiette appelée car encaissement non délégué » de `results/flux_commissions.json`.
- **Pourquoi personne ne l'avait vu.** `results/dbt_build.txt` datait de la veille de la reprise (153 réussites, 0 erreur).
  L'intégration continue n'exécute pas dbt, qui demande PostgreSQL et la chaîne de flux : un test de sévérité erreur
  pouvait donc rester rouge sans que rien ne le signale.
- **Ce que le défaut coûtait réellement.** Le modèle de recalcul est un contrôle, pas la source des commissions du
  tableau de bord (`fct_commissions` lit la table remplie par le code). Le défaut faisait donc échouer `dbt build`, ce
  qui arrête la tâche de publication des marts dans le graphe Airflow, et il signalait à tort une divergence sur 1 184
  appels. Mais le risque de fond est plus large : un décisionnel construit sur ce recalcul aurait affiché des
  commissions différentes de celles de l'ERP pour les mêmes appels, l'incohérence qu'un éditeur redoute entre son
  ERP et son décisionnel.
- **Correction.** Le modèle calcule `encaissement_est_delegue` à la date d'échéance, depuis les conventions et les actes
  délégués, et applique le repli D24 ; le second test ne contrôle plus l'encaissement rapproché dans ce cas. Les deux
  tests repassent, et la sortie complète de `dbt build` a été relancée (`results/dbt_build.txt`).
- **À retenir.** Toute règle de gestion écrite deux fois (code et SQL) doit avoir un test qui compare les deux, et ce
  test doit tourner à chaque changement de l'une ou de l'autre. Reste ouvert : faire exécuter dbt par l'intégration
  continue sur la base du compose.
