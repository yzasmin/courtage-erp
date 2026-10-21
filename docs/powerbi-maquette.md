Le tableau de bord de pilotage du cabinet : le modèle sémantique TMDL, les cinq pages du rapport et les visuels de chacune, avec les captures de l'ouverture réelle dans Power BI Desktop.

# Tableau de bord Power BI

Projet : `powerbi/Pilotage-Courtage.pbip`, format PBIP (modèle sémantique en TMDL, rapport en JSON), versionnable en texte. Le binaire `.pbix` n'est pas versionné. Les définitions des quatre indicateurs, avec leurs pièges, sont dans `docs/kpi.md`.

## Ce qui a été vérifié, et comment

| Vérification | Résultat | Preuve |
| --- | --- | --- |
| Le projet s'ouvre dans Power BI Desktop | oui, sans message d'erreur : le titre de la fenêtre est « Pilotage-Courtage », les 11 tables de données, la table de mesures et les 5 pages sont présentes | captures `docs/captures/08` à `12` |
| Le modèle se charge | oui : actualisation complète lancée par une commande TMSL sur le moteur local, terminée sans erreur | `scripts/executer_dax.ps1 -Actualiser` |
| Les mesures s'évaluent | oui : 3 requêtes DAX, 46 lignes de résultat | `results/powerbi/*.csv` |
| Les mesures donnent les mêmes valeurs que le SQL | oui : 302 comparaisons, 21 mesures, écart relatif maximal 2,9e-14 | `results/concordance_dax_sql.json`, tableau dans `docs/kpi.md` |

Version de Power BI Desktop mesurée sur le poste : **2.159.883.0**, installation Microsoft Store (`Get-AppxPackage` et version du fichier `PBIDesktop.exe`). C'est une version plus récente que la 2.157.1354.0 qui avait été annoncée : le projet a été vérifié sur celle qui est réellement installée.

Aucun fichier `.dax` « à coller » n'a été nécessaire, puisque l'ouverture a réussi. Les mesures restent lisibles dans `powerbi/mesures.dax`, qui est la source unique dont le modèle TMDL est généré.

## Le modèle sémantique

Modèle en étoile, produit par dbt (`dbt/models/marts/`), lu par Power BI dans des CSV exportés (`powerbi/donnees/`, non versionnés, régénérés par `make exporter-powerbi`). Les CSV plutôt qu'une connexion PostgreSQL : le projet s'ouvre sans pilote ni identifiant, et aucune donnée nominative n'y figure (ni nom, ni prénom, ni coordonnées d'adhérent).

| Table | Rôle | Grain |
| --- | --- | --- |
| `fct_cotisations_acquises` | cotisations acquises hors taxe, dénominateur du ratio sinistres sur primes | un appel par mois couvert |
| `fct_cotisations` | cotisations émises, pour la mesure de contrôle | un appel de cotisation |
| `fct_prestations` | prestations, numérateur du ratio | un remboursement |
| `fct_mouvements_portefeuille` | affaires nouvelles et résiliations | un mouvement |
| `fct_portefeuille_mensuel` | portefeuille à chaque fin de mois | un contrat par cliché |
| `dim_date` | calendrier, du premier avenant au 30/09/2026 | un jour |
| `dim_produit`, `dim_branche`, `dim_compagnie`, `dim_apporteur` | référentiel | une ligne par objet |
| `dim_adherent` | département et tranche d'âge à la date d'arrêt | un adhérent |
| `Mesures` | table technique qui porte les 26 mesures, sans donnée | |

Relations : 29, toutes de plusieurs vers un, des faits vers les dimensions. Une seule est inactive : `fct_prestations[date_soins]` vers `dim_date`, activée par `USERELATIONSHIP` dans la mesure de contrôle `[Contrôle ratio en date de soins]`. La relation active des prestations porte sur la date de règlement.

Choix du modèle, avec leur raison :

- **Deux faits de cotisation, émises et acquises.** Un seul fait obligerait à répartir les cotisations dans le DAX, à chaque évaluation, sur 71 415 lignes. Réparties dans dbt, testées une fois, elles sont lues en une somme.
- **Un cliché mensuel plutôt qu'un calcul dans le DAX.** Le portefeuille à une date se lit par une égalité sur la date du cliché. Le reconstituer depuis les avenants à chaque affichage serait lent et propice aux erreurs de borne.
- **Les mesures de stock (`[Contrats au portefeuille]`, `[Cotisation annualisée du portefeuille]`) lisent le cliché de la fin de la période** avec `REMOVEFILTERS ( dim_date )` : elles ne s'additionnent pas sur les mois, ce que montre la courbe de la page Portefeuille.
- **Un filtre de rapport `annee >= 2024`**, parce que le quittancement ne commence qu'en octobre 2023 : avant, les ratios n'ont pas de dénominateur.
- **Les segments d'année sont cochés sur 2025 à l'ouverture.** Sans sélection, les cartes cumulent 2024 à 2026 : le taux de résiliation affiché serait celui d'une cohorte suivie sur trois ans, qui n'est pas comparable à un taux annuel.

## Les pages et leurs visuels

Chaque page fait 1 280 par 720 pixels. Les quatre cartes d'indicateurs occupent le haut, les graphiques le milieu, les tableaux le bas, les segments (année, branche) la colonne de droite. 49 visuels en tout.

### Page 1, Synthèse (`08-powerbi-synthese.png`)

Pour la direction : les quatre chiffres, leur tendance, et la ventilation par branche.

| Visuel | Type | Contenu |
| --- | --- | --- |
| Quatre cartes | carte | `[Ratio sinistres sur primes]`, `[Taux de résiliation]`, `[Affaires nouvelles]`, `[Contrats au portefeuille]` |
| Ratio par trimestre | courbe | `[Ratio sinistres sur primes]` par `annee_trimestre` |
| Entrées et sorties par trimestre | colonnes | `[Affaires nouvelles]` et `[Résiliations toutes]` |
| Contrats par branche | colonnes | `[Contrats au portefeuille]` par branche |
| Les quatre indicateurs par année | tableau | les quatre mesures par année |
| Segments | segment | année, branche |

### Page 2, Sinistres sur primes (`09-powerbi-sinistres-primes.png`)

Pour la gestion des prestations : de quoi le ratio est fait.

| Visuel | Type | Contenu |
| --- | --- | --- |
| Quatre cartes | carte | ratio, prestations réglées du périmètre délégué, cotisations acquises du périmètre délégué, ratio sur cotisations émises (contrôle) |
| Prestations et cotisations acquises par année | colonnes | les deux montants, côte à côte |
| Ratio par trimestre | courbe | date de règlement et date de soins sur le même graphique |
| Ratio par branche | tableau | prestations, acquises, ratio |
| Ratio par compagnie | tableau | prestations, acquises, ratio |

### Page 3, Résiliations (`10-powerbi-resiliations.png`)

Pour la fidélisation : à qui et pourquoi.

| Visuel | Type | Contenu |
| --- | --- | --- |
| Quatre cartes | carte | taux, taux annualisé, résiliations de la cohorte, portefeuille en début de période |
| Résiliations par motif | colonnes | motif de résiliation, trié par volume |
| Résiliations par tranche d'âge | colonnes | tranche d'âge **au moment de la résiliation** |
| Taux par année | tableau | cohorte, toutes résiliations, effectif de début, taux, taux annualisé |
| Taux par produit | tableau | cohorte, effectif de début, taux |

### Page 4, Production par apporteur (`11-powerbi-production-apporteur.png`)

Pour le réseau de distribution : qui apporte quoi.

| Visuel | Type | Contenu |
| --- | --- | --- |
| Quatre cartes | carte | affaires nouvelles, cotisation annualisée, cotisation annualisée moyenne par affaire, variation nette du portefeuille |
| Cotisation annualisée par apporteur | barres | trié par cotisation annualisée décroissante |
| Production par apporteur | tableau | affaires, cotisation annualisée, moyenne, part de la production |
| Affaires par mois | colonnes | `[Affaires nouvelles]` par mois |

### Page 5, Portefeuille par branche (`12-powerbi-portefeuille-branche.png`)

Pour le pilotage du portefeuille : ce que le cabinet gère aujourd'hui.

| Visuel | Type | Contenu |
| --- | --- | --- |
| Quatre cartes | carte | contrats au portefeuille, cotisation annualisée, dont suspendus, cotisation annualisée moyenne par contrat |
| Cotisation annualisée par branche | barres | `[Cotisation annualisée du portefeuille]` |
| Contrats à chaque fin de mois | courbe | `[Contrats au portefeuille]` par mois : un stock, lu cliché par cliché |
| Portefeuille par branche | tableau | contrats, suspendus, cotisation annualisée, moyenne |
| Portefeuille par tranche d'âge | tableau | contrats et cotisation annualisée par tranche d'âge de l'adhérent |
| Segments | segment | année, département |

## Ouvrir le projet

1. `make marts-pilotage` puis `make exporter-powerbi` : produisent `powerbi/donnees/*.csv`.
2. `make pbip DONNEES="C:\chemin\vers\courtage-erp\powerbi\donnees"` : réécrit le paramètre `DossierDonnees` du modèle. Power BI n'accepte pas de chemin relatif ; le projet versionné porte un chemin d'exemple, à adapter après un clone.
3. Ouvrir `powerbi/Pilotage-Courtage.pbip` (chemin long entre guillemets, un chemin court 8.3 est refusé), puis Accueil, Actualiser. Ou, depuis PowerShell, `scripts/executer_dax.ps1 -Actualiser`, qui lance l'actualisation par TMSL puis évalue les requêtes de `powerbi/controles/`.

## Limites assumées

- **Le niveau absolu du ratio sinistres sur primes n'est pas réaliste** (plus de 100 %) : c'est le calibrage du générateur de données, expliqué dans `docs/kpi.md`. Le tableau de bord le montre tel quel plutôt que de le masquer.
- **Les tableaux des pages sont étroits** : sur la mise en page de 1 280 pixels, les colonnes de droite se lisent en faisant défiler. Les captures sont prises à 59 % de zoom.
- **Les segments d'année ne sont pas synchronisés entre les pages** : chaque page porte le sien, coché sur 2025.
- **Aucune actualisation planifiée** : les CSV sont régénérés à la demande. Un déploiement réel passerait par une connexion directe à la base et une passerelle de données, ce que ce projet ne fait pas.
- **Aucune sécurité par ligne** : tout utilisateur du rapport voit tous les apporteurs. Un partage avec le réseau demanderait une règle par apporteur.
- **La mise en page a été vérifiée sur une seule résolution** (fenêtre de 1 720 par 820 pixels).
