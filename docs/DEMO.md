Le parcours de deux minutes et demie à montrer en entretien, écran par écran, avec les mots à dire et les commandes à taper.

# Démonstration de deux minutes et demie

Le parcours suit les questions qu'un gestionnaire de courtier délégataire se pose un lundi matin : où en est
mon contrat, quel fichier a-t-on refusé, qu'ai-je le droit de faire pour cette compagnie, et qu'est-ce que
cela donne en chiffres pour la direction. Il ne montre que ce qui existe. Le module 4b (conditions
générales) n'est pas réalisé : si on l'évoque, c'est pour le dire. Les deux écrans des modules 4a et 5, l'agent de pré-remplissage et le score de
résiliation, ont chacun leur étape dans le parcours.

## Avant l'entretien : préparer le poste

La pile n'a pas besoin d'être démarrée à l'avance, mais elle ne se démarre pas devant l'interlocuteur. Deux
préparations au choix. Dans les deux cas, ouvrir un terminal Git Bash.

### Chemin A, sans Docker, sur SQLite

Prérequis : Python 3.12 et `uv` (`python -m pip install uv`). `make` n'est pas nécessaire : les commandes
ci-dessous sont celles que lancent les cibles du `Makefile`, et `make` n'est pas installé par défaut sous
Windows. C'est le chemin à prendre sur une machine inconnue. Il ne montre ni Airflow ni les marts dbt en
direct, ces deux écrans passent par les captures de `docs/captures/`, et **il ne montre pas le score de
résiliation** : les variables du modèle sont construites par dbt, qui demande PostgreSQL. Sur ce chemin,
l'étape du score passe par la capture `docs/captures/14-fiche-adherent-score.png`.

```bash
git clone https://github.com/yzasmin/courtage-erp.git && cd courtage-erp
python -m uv sync --frozen --extra ml --extra ia
python -m uv run courtage migrer
python -m uv run courtage generer --si-vide       # 14,30 s mesurées sur le poste de développement
python -m uv run courtage flux generer            # dépose le courrier simulé du mois
python -m uv run courtage flux chaine             # contrôles, rapprochement, commissions, bordereaux
python -m uv run courtage ia traiter              # 30 dossiers à valider, réponses enregistrées, sans clé
python -m uv run courtage servir                  # http://127.0.0.1:8000
```

`flux chaine` réécrit les comptes rendus de `results/` : sur un clone, c'est sans conséquence, mais ne pas la
lancer dans le dépôt de travail sans y penser. Sans cette étape, l'écran des anomalies annonce que la chaîne
n'a jamais été exécutée, ce qui est le comportement voulu mais pas celui qu'on veut montrer.

### Chemin B, avec Docker, sur PostgreSQL

Prérequis : Docker Desktop démarré. C'est le chemin qui montre Airflow en direct et le score de résiliation.

```bash
docker compose up -d --build
docker compose exec airflow-scheduler airflow dags unpause courtage_flux_financiers
docker compose exec airflow-scheduler airflow dags trigger courtage_flux_financiers
# une fois le graphe des flux au vert, qui a construit les marts dont le score a besoin :
docker compose exec airflow-scheduler airflow dags unpause courtage_scoring_resiliation
docker compose exec airflow-scheduler airflow dags trigger courtage_scoring_resiliation
docker compose run --rm erp-cli courtage ia traiter
```

Attendre que `docker compose ps` montre l'application en bonne santé, puis que les deux graphes soient au
vert dans Airflow (http://127.0.0.1:8080, compte `admin`, mot de passe `courtage`). La première construction
des images est la partie longue : la faire la veille. L'ERP répond sur http://127.0.0.1:8000.

## Le parcours, minute par minute

Total visé : 150 secondes. Chaque étape donne le temps, l'écran, ce qu'il faut dire et ce qu'il faut cliquer.

### 0 min 00, accueil (10 s)

Écran : http://127.0.0.1:8000.

Dire : « Un courtier grossiste délégataire gère au nom des compagnies. Ce mini-ERP simule ce métier sur
5 737 contrats et trois ans d'historique, toutes données synthétiques. J'ai travaillé sur des migrations de
données vers un ERP et des imports par API, c'est ce qui a décidé de ce que je montre : les contrôles avant
écriture. »

### 0 min 10, fiche contrat et historique des avenants (25 s)

Écran : menu Portefeuille, ouvrir le contrat `SI-2020-00056`, puis descendre à l'historique des avenants.
Ouvrir ensuite dans un second onglet :

```
http://127.0.0.1:8000/api/v1/contrats/SI-2020-00056/etat?a_la_date=2022-03-01
http://127.0.0.1:8000/api/v1/contrats/SI-2020-00056/etat?a_la_date=2022-08-01
```

Dire : « Un contrat change de tarif, de formule, d'apporteur. Chaque événement est un avenant, et l'état à
une date se reconstitue en relisant les avenants. Ici, le même contrat coûte 72,86 euros par mois en mars
2022 et 50,87 euros en août, après un changement de formule, et la réponse dit de quel avenant vient la
valeur. C'est ce qui permet de recalculer une commission trois ans plus tard au bon taux. »

Si une valeur affichée diffère de ces montants, la base n'est pas celle de la graine `20261019` : le dire
plutôt que de commenter un autre chiffre.

### 0 min 35, anomalies de rapprochement (25 s)

Écran : menu Anomalies.

Dire : « La chaîne a reçu 27 fichiers du mois : bordereaux de cotisations, relevé bancaire, retours de
prestations. Neuf ont été rejetés en entier par les contrôles bloquants, chacun pour un motif nommé : un
fichier déjà chargé, un total qui ne tombe pas juste, un acte non délégué. Un lot rejeté ne laisse aucune
ligne en base, et le fichier part avec son rapport d'anomalies, qui est la pièce à renvoyer à l'émetteur. En
dessous, les 50 écarts de rapprochement : on voit si la correspondance s'est faite par référence ou par
montant et date, parce qu'une correspondance par montant est une présomption. »

Montrer du doigt : les tuiles du haut (9 lots rejetés, 50 écarts, 24 mouvements sans appel) et la colonne
« Motif du rejet ».

### 1 min 00, dossiers à valider, l'agent de pré-remplissage (30 s)

Écran : menu Dossiers à valider.

Dire : « Les documents reçus, demandes de remboursement, factures d'opticien, notes de dentiste, attestations
d'employeur, sont lus par un modèle de langage qui remplit dix champs dans un format imposé. Il lit, il ne
décide pas : les contrôles sont écrits en code et rien n'entre au portefeuille sans décision d'un
gestionnaire. Sur trente documents, 96,7 % des champs sont exacts, les huit anomalies glissées exprès sont
relevées, pour 0,03 centime de dollar par document. »

Montrer : un dossier avec l'alerte « nom approchant » (`doc-03`), un dossier bloqué pour total faux
(`doc-15`, sans bouton Valider), puis cliquer Valider sur un dossier sain (`doc-16`) : le message cite la
prestation créée.

### 1 min 30, réseau et délégations, le refus (20 s)

Écran : menu Réseau, repérer la convention du produit prévoyance incapacité et invalidité, arrivée à
échéance le 30/06/2026. Puis menu Saisir un contrat, produit `PV-ARRET`, date de souscription postérieure au
30/06/2026, valider.

Dire : « Chaque compagnie délègue un périmètre d'actes différent, par convention datée. Celle-ci a expiré et
n'a pas été renouvelée dans le jeu. La saisie est refusée avant toute écriture, avec le motif « aucune
convention de délégation en vigueur pour ce produit », et la saisie est conservée pour ne pas être retapée. La règle est dans le service, donc elle
vaut aussi pour l'API et pour un script d'import. »

### 1 min 50, fiche adhérent et score de résiliation (15 s)

Écran, chemin B : http://127.0.0.1:8000/adherents/A004928. Écran, chemin A : la capture
`docs/captures/14-fiche-adherent-score.png`.

Dire : « Chaque mois, chaque contrat reçoit un score de risque de résiliation et les trois raisons qui le
poussent, dites comme un gestionnaire les dirait : ici une revalorisation de 6,2 %, un apporteur en ligne,
dix mois d'ancienneté. Les données sont synthétiques ; ce qui compte est l'absence de fuite d'information et
le choix du modèle simple, parce que le modèle complexe ne faisait pas mieux. »

### 2 min 05, orchestration et lineage (10 s)

Écran, chemin B : Airflow, graphe `courtage_flux_financiers`. Écran, chemin A : la capture
`docs/captures/08-graphe-airflow.jpg`, puis `docs/captures/07-lineage-dbt-commissions.jpg`.

Dire : « Chaque tâche du graphe appelle une commande et lit son code de retour, donc la chaîne se rejoue à la
main sur un poste sans Airflow. Côté dbt, on remonte d'une commission à l'appel de cotisation qui l'a
produite. Un lot rejeté fait échouer la dernière tâche, pour que le rejet se voie. »

La capture du graphe date d'avant l'ajout de la tâche `alerter` : le graphe actuel compte quatorze tâches, la
capture en montre treize. Le dire si on la commente.

### 2 min 15, pilotage (10 s)

Écran : `docs/captures/08-powerbi-synthese.png`. Le projet Power BI se rouvre depuis `powerbi/` avec
`make pbip DONNEES=<chemin>`, mais ce n'est pas un geste de démonstration.

Dire : « Quatre indicateurs, définis une fois dans `docs/kpi.md` avec leurs pièges chiffrés. Le ratio de
sinistres sur primes de 2025 vaut 79,99 %. Les 302 comparaisons entre les mesures Power BI et le SQL de
contrôle ont un écart relatif maximal de 2,9e-14. »

### 2 min 25, fin

Une phrase de clôture : « La recherche dans les conditions générales n'est pas faite, et le README le dit. Tout le reste se rejoue
par les commandes du `Makefile`, et chaque chiffre vient d'un fichier de `results/`. »

## Si quelque chose ne marche pas

| Symptôme | Cause probable | Que faire |
| --- | --- | --- |
| L'écran Anomalies dit que la chaîne n'a jamais été exécutée | `flux chaine` non lancée | La lancer, recharger la page |
| Le port 8000 est occupé | une autre application | `python -m uv run courtage servir --port 8001` |
| `make` n'existe pas (PowerShell) | Git Bash non utilisé | Reprendre la commande de chaque cible dans le `Makefile` |
| Airflow ne répond pas | pile Docker non démarrée ou graphe non déclenché | Chemin A : passer aux captures |
| Un chiffre diffère de ce document | base générée avec une autre graine | `python -m uv run courtage empreinte`, comparer à l'empreinte de `docs/PROGRESS.md` |

## Questions probables, et où est la réponse

- Pourquoi des avenants plutôt qu'une table d'historique : `docs/DECISIONS.md`, D10.
- Pourquoi des montants en centimes : D06.
- Que se passe-t-il si la compagnie encaisse elle-même : D24, et la limite correspondante dans le README.
- Pourquoi le ratio sinistres sur primes a changé : `docs/PROGRESS.md`, section « Recalibrage de la
  sinistralité », et D32.
- Ce que couvre le jeu : santé individuelle, santé collective, prévoyance. Ni automobile ni dommages.
