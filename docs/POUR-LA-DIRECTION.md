Une page qui relie chaque module livré à un besoin concret d'un éditeur de logiciel de courtage délégataire, avec la preuve et la limite de chacun.

# Pour la direction d'un éditeur de logiciel de courtage

Ce dépôt est un démonstrateur : un mini-ERP de courtage santé et prévoyance, sur un portefeuille simulé de
5 737 contrats, produit par le dépôt lui-même à graine fixe. Il n'est pas un produit, il ne contient aucune
donnée réelle et il ne suppose rien sur la pile technique ni sur le périmètre fonctionnel d'un éditeur
précis. Il montre une manière de traiter six problèmes de gestion que rencontre un courtier grossiste
délégataire, et chaque affirmation ci-dessous renvoie à un fichier de `results/` ou à un test.

## Besoin par besoin

| Besoin d'un éditeur de logiciel | Ce que le dépôt en montre | Preuve | Ce que cela ne démontre pas |
| --- | --- | --- | --- |
| Gérer au nom de la compagnie, dans un périmètre d'actes défini par convention, produit par produit | Une convention de délégation porte une portée, des actes et des dates de validité. Le service refuse l'acte non délégué avant d'écrire. Trois portées différentes et une convention expirée sont dans le jeu | `tests/test_delegation.py`, `docs/modele-donnees.md` | Les conventions réelles d'un éditeur et leurs actes propres : les périmètres du jeu sont des hypothèses |
| Dire dans quel état était un contrat à une date donnée, des années plus tard | Chaque changement est un avenant daté. L'état à une date se reconstitue, et la réponse indique l'avenant d'origine | `tests/test_avenants.py`, `results/coherence_metier.json` (18 contrôles conformes) | Une reprise de données historiques réelles, avec ses trous |
| Paramétrer par produit sans modifier le code | Taux de taxe, de commission, de rétrocession, formules et plafonds sont des lignes en base avec leurs dates de validité | `docs/HYPOTHESES.md` | Un écran d'administration des paramètres : il n'en existe pas, les paramètres se modifient en base |
| Refuser un fichier douteux et garder la trace de ce qui a été reçu | Huit contrôles bloquants avant toute écriture, rejet du lot entier, empreinte SHA-256 de chaque fichier, archive, journal par lot | `results/flux_rejet_integral.json` : 9 lots rejetés sur 27, aucune ligne écrite ; `results/flux_idempotence.json` : 27 fichiers redéposés, état identique | Des formats de fichier réels, que les compagnies envoient chacune à leur manière |
| Savoir ce qui a été encaissé et ce qui ne l'a pas été | Rapprochement par référence, puis par montant et date dans une fenêtre paramétrable, avec la méthode conservée sur chaque ligne | `results/flux_rapprochement.json` : 2 588 lignes examinées : 2 488 rapprochées, 34 partielles, 16 en écart, 24 sans appel correspondant, 26 ignorées car l'acte n'est pas délégué | Le rapprochement bancaire d'un cabinet réel et ses libellés de virement |
| Calculer commissions et rétrocessions au bon taux, et éditer les bordereaux | Taux valide à la date d'échéance de l'appel, pas à la date du calcul. Bordereaux mensuels par compagnie et par apporteur, en base et en CSV | `results/flux_commissions.json` : 3 704 commissions pour 79 346,83 euros, 2 978 rétrocessions pour 38 895,54 euros ; `results/flux_bordereaux.json` : 33 bordereaux | Le bordereau de commissions que la compagnie adresse au cabinet n'est pas ingéré : sur 1 184 appels, l'assiette de repli est la cotisation appelée hors taxe (décision D24) |
| Piloter l'activité avec des indicateurs que la direction et la gestion lisent de la même façon | Quatre indicateurs définis une fois, avec leurs pièges chiffrés, une requête SQL de contrôle chacun, et un tableau de bord Power BI | `docs/kpi.md`, `results/kpi_sql.json`, `results/concordance_dax_sql.csv` : 302 comparaisons entre mesures et SQL, écart relatif maximal 2,9e-14 | Des valeurs de marché : le ratio sinistres sur primes de 76,38 % en 2024 est celui d'un générateur calibré par hypothèse |
| Ne plus ressaisir les documents reçus, sans laisser un modèle écrire dans le portefeuille | Lecture par un modèle de langage en sortie structurée stricte, contrôles métier écrits en code, dossier à valider ; la validation passe par le service de saisie existant | `docs/eval-extraction.md`, `results/ia_evaluation.json` : 96,7 % des champs exacts sur 30 documents, 8 anomalies sur 8 relevées, 0,00027 $ par document | La lecture de scans ou de photos : les documents de démonstration ont un texte net |
| Savoir quels adhérents risquent de partir à l'échéance, et pourquoi, à temps pour les appeler | Un score mensuel par contrat, son décile et les trois facteurs qui l'expliquent, sur la fiche adhérent. Variables calculées sans information postérieure, modèle mesuré sur une année qu'il n'a pas vue | `docs/eval-resiliation.md`, `results/ml_resiliation.json` : ROC-AUC 0,645 sur 2025 pour un plafond de 0,662 | Une performance sur un vrai portefeuille : les causes de résiliation du jeu sont celles que le générateur y a mises |
| Installer et faire évoluer le schéma chez un client sans perdre de données | Migrations qui montent et redescendent sans résidu, même code sur PostgreSQL et SQLite, jeu de données identique octet pour octet sur les deux | `results/migrations_postgresql.json`, `results/reproductibilite_postgresql.json` (empreinte identique à SQLite) | Une migration depuis un autre logiciel, que le dépôt ne contient pas |

## Les trois lectures utiles

**Le rejet intégral.** Un lot dont une ligne viole une règle bloquante n'écrit rien. C'est le point où les
reprises de données et les imports par interface se détériorent le plus souvent : un chargement à moitié fait
se découvre trois semaines plus tard. Sur les 27 lots du jeu, 9 sont rejetés, et la preuve vérifie en base
que 0 ligne en est restée.

**Les pièges d'indicateurs.** Le ratio sinistres sur primes de 2024 vaut 76,38 % rapporté aux cotisations
acquises des produits dont les prestations sont déléguées, et 54,25 % rapporté à tous les produits. Les
deux chiffres sont justes, ils ne répondent pas à la même question (`results/kpi_sql.json`, `01b`). Écrire la
définition une fois et la contrôler en SQL évite que la direction et la gestion débattent de chiffres
différents.

**La reproductibilité.** Deux exécutions de même graine donnent la même empreinte, sur les deux moteurs. Une
anomalie signalée est donc rejouable par n'importe qui, ce qui sert autant à un support qu'à une recette.

## Ce que ce dépôt ne couvre pas

- **Le module 4b n'est pas fait** : pas de recherche dans les conditions générales.
- **Aucune authentification ni gestion de droits.** L'interface et l'API sont ouvertes sur la boucle locale.
- **Pas d'automobile ni de dommages.** Santé individuelle, santé collective, prévoyance.
- **Pas de connexion à un concentrateur de tiers payant.** Les retours de prestations sont des fichiers
  simulés, et le bordereau de prestations émis vers la compagnie n'est pas modélisé (D22 et D23).
- **Pas de volume de production.** 5 737 contrats, trois ans d'historique, sur un poste de 8 Go.
- **Aucune supposition sur votre pile.** Le dépôt est en Python, PostgreSQL, dbt et Airflow parce que c'est
  ce que son auteure maîtrise, pas parce que cela convient à votre environnement.

## Ce qu'un éditeur de petite taille peut en retenir

La chaîne se rejoue par une commande sur un poste sans Airflow ni Docker (`courtage flux chaine`), et la pile
complète tient dans une machine virtuelle Docker de 3,75 Go, avec environ 1 567 Mio utilisés au
moment le plus chargé (`docs/DECISIONS.md`, section « Dimensionnement des conteneurs »). Rien n'oblige donc à
monter une plateforme pour utiliser une brique : le contrôle des fichiers reçus, le rapprochement ou le
calcul des indicateurs se prennent séparément.

La démonstration de deux minutes est dans `docs/DEMO.md`, l'état réel du projet dans `docs/PROGRESS.md`.
