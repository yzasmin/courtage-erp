Documentation du module 2 : la chaine des flux financiers, de la reception des bordereaux au bordereau de retrocession de l'apporteur.

# Flux financiers : reception, controles, rapprochement, commissions

## Le probleme de gestion

Un courtier grossiste delegataire recoit, chaque mois, trois sortes de courrier financier.

1. Le **bordereau de cotisations**, envoye par chaque compagnie, qui recapitule ce qui a ete quittance
   au nom de celle-ci sur la periode.
2. Le **releve d'encaissements**, envoye par la banque, qui dit ce qui est reellement entre sur le
   compte du cabinet.
3. Le **bordereau de prestations**, qui restitue au cabinet les remboursements regles pour le compte
   d'une compagnie, et qui vient du **concentrateur de tiers payant**, pas de la compagnie.

Le troisieme point merite d'etre explicite, parce que ce document a d'abord ecrit le contraire. Une
compagnie qui a delegue la gestion des prestations ne les gere plus : elle ne peut donc pas en envoyer
le bordereau. Le sens reel des flux est l'inverse, et il a deux branches :

- **ce qui entre** : les prestations reglees dans le circuit du tiers payant, que le concentrateur
  restitue au delegataire par flux de retour, contrat par contrat, donc regroupees par compagnie
  porteuse du risque. C'est ce fichier que la chaine ingere, et c'est pourquoi son nom porte le code
  de la compagnie : il designe le perimetre des contrats concernes, pas l'expediteur ;
- **ce qui sort** : le bordereau que le cabinet **emet** vers la compagnie pour se faire rembourser
  les prestations qu'il a reglees pour son compte. Ce flux sortant n'est pas modelise ici, et c'est
  une limite assumee, consignee dans `docs/DECISIONS.md`.

La chaine de ce module ne traite donc que des flux entrants, ce qui est coherent : un delegataire
controle ce qu'il recoit avant de l'integrer, et ce controle est le sujet du module.

De ce courrier, le cabinet doit tirer trois choses avant de pouvoir facturer quoi que ce soit :

1. savoir quelles cotisations appelees ont ete reellement encaissees, et lesquelles ne l'ont pas ete ;
2. calculer les commissions que les compagnies lui doivent, sur la bonne assiette et au bon taux ;
3. editer le bordereau de retrocession de chacun de ses apporteurs.

Fait a la main, ce travail occupe plusieurs jours par mois et il se trompe. Les erreurs ne sont pas
reparties au hasard : elles se concentrent sur les lignes qu'un oeil humain ne verifie pas, un fichier
charge deux fois, une quittance hors periode de garantie, un total de bordereau qui ne tombe pas juste.
C'est ce travail que ce module automatise, et surtout c'est ce controle qu'il rend systematique.

## La chaine, etape par etape

| Etape | Commande | Ce qu'elle fait, et ce qu'elle refuse |
| --- | --- | --- |
| detection | `courtage flux detecter` | inscrit au journal chaque fichier present, avec son empreinte SHA-256 |
| archivage | `courtage flux archiver` | deplace le brut dans l'archive, et verifie que l'empreinte n'a pas change |
| chargement | `courtage flux charger` | applique les controles, charge la couche brute **ou** rejette le lot entier |
| transformations | `dbt build --select staging intermediaire` | couches dbt et tests de qualite |
| rapprochement | `courtage flux rapprocher` | par reference, puis par montant et date dans une fenetre parametrable |
| commissions | `courtage flux commissions` | commissions et retrocessions, au taux valide a la date d'echeance |
| bordereaux | `courtage flux bordereaux` | bordereaux mensuels, par compagnie et par apporteur |
| publication | `dbt build --select marts` | marts, qui refletent les commissions venant d'etre calculees |
| documentation | `dbt docs generate` | documentation et lineage |
| comptes rendus | `courtage flux rapport`, `courtage flux journal` | rappel et precision des anomalies, journal par lot |
| alerte | `courtage flux alerter` | **echoue** si le depot du jour contient un lot rejete, pour que le rejet se voie dans Airflow |

`courtage flux chaine` enchaine toutes les etapes hors dbt, sur un poste sans Airflow ni Docker.

### Pourquoi quatorze taches et non une

Chaque tache echoue pour une raison differente et se reprend a un endroit different. Un depot incomplet
fait echouer l'archivage, une base indisponible fait echouer le chargement, un modele dbt casse fait
echouer les transformations. L'etat d'avancement est porte par la colonne `statut` de `lot_fichier`,
donc une reprise apres echec reprend chaque lot ou il en etait au lieu de recommencer au depot.

### Pourquoi la publication des marts vient apres le calcul des commissions

Les marts exposent les commissions. Les construire avant le calcul les publierait vides au premier
passage du mois. Le graphe fait donc deux appels a `dbt build` : les couches staging et intermediaire
avant les calculs, les marts apres.

### Pourquoi le graphe n'importe aucun code metier

Chaque tache appelle un executable dans un environnement virtuel dedie, `courtage` pour la chaine
metier et `dbt` pour les transformations. Airflow contraint strictement ses dependances, et
l'application ERP utilise SQLAlchemy 2 : les faire cohabiter dans un meme environnement rend
l'installation fragile, et la premiere montee de version la casse. Les deux mondes ne se rencontrent
donc qu'a travers une ligne de commande et un code de retour.

Benefice secondaire, et il compte pour la demonstration : chaque etape s'execute aussi a la main, sur
un poste sans Airflow.

## Les controles

### Bloquants : un echec rejette le lot entier

| Controle | Pourquoi il est bloquant |
| --- | --- |
| schema et types | une ligne illisible rend le bordereau non rapprochable |
| fichier deja charge, par empreinte | charger deux fois le meme bordereau double cotisations et commissions |
| doublon de cle metier | deux lignes pour une meme quittance : on ne sait pas laquelle est bonne |
| contrat ou police inconnu | la compagnie quittance un contrat que le cabinet ne gere pas : defaut de perimetre |
| adherent inconnu | meme raison |
| somme des lignes differente de la ligne de total | le fichier est tronque ou altere, aucune ligne n'est fiable |
| periode incoherente avec l'effet ou la resiliation | quittancer hors garantie expose le cabinet et fausse le ratio sinistres sur primes |
| acte non delegue | la convention est echue : le cabinet n'a plus le droit d'accomplir cet acte |

Le huitieme ne figure pas dans la specification, et il est le plus caracteristique du metier vise. Un
courtier delegataire accomplit au nom de la compagnie des actes qui appartiennent normalement a
l'assureur, dans le perimetre d'une convention datee. Quand la convention est echue, le cabinet doit
cesser ces actes, meme si la compagnie continue d'envoyer ses bordereaux.

### Non bloquants : journalises, le lot passe

| Controle | Ce qu'il signale |
| --- | --- |
| montant atypique | le tarif mensuel par affilie s'ecarte fortement de la mediane des echeances connues du porteur |
| prestation proche du plafond | cette prestation fait franchir a la consommation annuelle le seuil d'alerte de la garantie |

### Comment le rejet integral est garanti

La garantie est structurelle, et pas seulement intentionnelle. Les controles sont executes **en
totalite avant la premiere ecriture**. Quand un lot est rejete, le code qui insere les lignes n'est tout
simplement pas atteint : il n'y a pas d'ecriture a annuler. Trois filets s'ajoutent :

1. chaque lot est traite dans sa propre transaction, donc le rejet d'un bordereau ne touche pas les
   autres, et un cabinet ne bloque pas son mois parce qu'une compagnie a mal exporte ;
2. la contrainte `ck_lot_fichier_rejet_sans_ecriture_partielle` refuse en base un lot rejete qui
   annoncerait des lignes chargees ;
3. un test dbt de severite erreur, `assert_lot_rejete_sans_ligne_brute`, relit les lignes reellement
   presentes en couche brute, et non le compteur du journal.

La preuve mesuree est dans `results/flux_rejet_integral.json`, et un test par controle bloquant compte
les lignes avant et apres le chargement (`tests/flux/test_controles_bloquants.py`).

## Le rapprochement

L'ordre impose par la specification est respecte, et les deux methodes n'ont pas la meme valeur de
preuve.

1. **Par reference.** La ligne de releve porte la reference de l'appel. C'est une certitude.
2. **Par montant et date.** A defaut, parmi les appels du meme porteur, ceux dont l'echeance tombe dans
   la fenetre de tolerance et dont le montant correspond. C'est une presomption. Plusieurs candidats
   sont possibles sur un contrat mensuel a cotisation constante : l'echeance la plus proche du mouvement
   l'emporte, et le plus petit identifiant tranche une egalite, pour que deux executions donnent le meme
   resultat.

La methode employee et la fenetre utilisee sont conservees ligne a ligne, dans `rapprochement_ligne`.
Un gestionnaire qui instruit un litige doit savoir laquelle des deux il relit.

| Statut | Quand |
| --- | --- |
| `rapproche` | un appel trouve, montant encaisse egal au montant appele |
| `partiel` | un appel trouve, montant inferieur mais au-dessus de la part minimale |
| `ecart` | un appel trouve, montant superieur, ou trop faible pour etre un acompte |
| `non_trouve` | aucun appel ne correspond, ni par reference ni par montant et date |

**La delegation est opposee avant tout traitement.** Un mouvement rattache a un contrat dont la
compagnie n'a pas delegue l'encaissement n'est pas rapproche, meme si le fichier le contient et meme si
un appel correspondrait. Ces lignes sont comptees a part et figurent au journal. Le releve bancaire
n'est pas rejete pour autant : l'argent est arrive, c'est un fait, et rejeter un releve de huit cents
lignes parce qu'un adherent a paye le cabinet par erreur serait disproportionne. Ce qui serait un acte,
c'est d'affecter ce mouvement, et c'est cela qui est refuse.

## Les commissions

Trois regles, et chacune engage le cabinet devant une compagnie ou devant un apporteur.

**L'assiette est la cotisation encaissee, hors taxe.** Hypothese de simulation documentee, et surtout
**parametre en base** : la colonne `assiette` de `taux_commission` accepte aussi la cotisation appelee,
et le calcul la respecte. Les deux pratiques existent dans le metier, et un cabinet qui lirait ce code
doit pouvoir y retrouver la sienne sans le modifier. Un reglement partiel donne une assiette au prorata,
la cotisation et la taxe etant reglees dans la meme proportion. Un trop percu n'est pas commissionnable :
l'assiette est plafonnee a l'appel.

**Le taux retenu est celui en vigueur a la date d'echeance de l'appel.** Une echeance de janvier
commissionnee en avril applique le bareme de janvier. Sans cela, une revalorisation du bareme
reecrirait les bordereaux deja regles.

**L'apporteur retenu est celui en vigueur sur le contrat a la date d'echeance**, reconstitue par les
avenants. Sur une police collective, c'est l'apporteur de la police : une police n'a pas d'avenants dans
ce modele, et c'est une limite assumee.

Quand la compagnie n'a pas delegue l'encaissement, le cabinet ne sait pas ce qui a ete encaisse, donc il
ne peut pas commissionner sur une assiette encaissee. Ces appels sont ecartes et comptes, avec leur
motif, dans `results/flux_commissions.json`. Les commissionner a zero en silence produirait un bordereau
vide dont personne ne comprendrait la cause. Un cabinet reel configurerait ces produits sur l'assiette
**appelee**, ce que le modele permet deja.

### Les bordereaux

Deux documents par mois, et le vocabulaire compte.

- Le **bordereau de commissions** recapitule ce que la compagnie doit au cabinet. Destinataire : la
  compagnie. Reference `BC-<compagnie>-<AAAAMM>`.
- Le **bordereau de retrocessions** recapitule ce que le cabinet doit a l'un de ses apporteurs. C'est le
  document que la specification appelle « bordereau de commissions mensuel par apporteur », et celui
  qu'un apporteur attend chaque mois. Destinataire : l'apporteur. Reference `BR-<apporteur>-<AAAAMM>`.

Les deux sont ecrits en base, dans la table `bordereau`, et exportes en CSV dans
`data/flux/bordereaux/<AAAAMM>/`. Le total est recalcule avant l'ecriture et compare a la somme des
lignes ; un ecart leve une erreur et arrete le graphe, plutot que d'envoyer un document faux.

## Le projet dbt

Trois couches, une raison par couche.

| Couche | Materialisation | Role |
| --- | --- | --- |
| `staging` | vues | une vue par table source, qui renomme et type. Aucune regle metier. C'est le seul endroit qui connait la forme physique des tables |
| `intermediaire` | vues | les jointures et les regles de gestion : appels enrichis, etat du rapprochement, qualite des lots, commissions attendues |
| `marts` | tables | le modele en etoile servi au pilotage. En tables, parce que Power BI les interroge |

Les montants restent en centimes entiers jusqu'aux marts, et sont exposes en euros dans les marts. La
conversion a un seul endroit, a la frontiere de la restitution.

Un modele merite une mention : `int_commissions_attendues` **recalcule la commission en SQL**, depuis
les memes baremes dates que le code applicatif. Un test de severite erreur compare les deux. Deux
chemins de calcul independants qui divergent signalent une erreur dans l'un des deux, et c'est le seul
moyen de la trouver sans la reproduire.

Ce recalcul doit suivre chaque regle que le code applique. Il avait ete laisse en arriere sur la regle D24
(commission sur la cotisation appelee quand la compagnie encaisse elle-meme) : deux tests echouaient sur
1 184 appels. Il la reprend depuis le module 3, est materialise en table, et la lecon est dans
`docs/lessons/p8-sql-et-application-appliquent-la-meme-regle.md`.

Les tests de severite erreur portent sur l'identite des objets et sur les invariants du calcul. Les
quatre tests de severite avertissement portent sur des jugements de gestion et laissent passer le build.

## Le generateur de fichiers recus et son manifeste

Les fichiers sont construits a partir du portefeuille reellement genere au module 1, donc ils sont
coherents avec lui. Les anomalies sont de deux familles, qui ne se melangent pas :

- les **anomalies de ligne non bloquantes**, semees a hauteur de la part visee sur l'ensemble des
  lignes ;
- les **anomalies bloquantes**, posees lot par lot et non tirees au hasard, une seule par lot. Une
  anomalie bloquante rejette le lot entier : en semer au hasard reviendrait a rejeter la moitie du
  courrier. Chaque controle bloquant est exerce au moins une fois.

Pour chaque lot rejete, le generateur produit aussi le **fichier corrige** que l'emetteur renvoie, sous
un autre nom. La chaine montre ainsi la boucle complete du metier : rejet integral, renvoi, chargement.
Et un lot sain est redeposse octet pour octet sous un autre nom, pour exercer le controle d'empreinte.

Le releve bancaire est volontairement imparfait, et chaque imperfection sert a exercer un chemin :

| Ce qui est injecte | Chemin exerce |
| --- | --- |
| une part des lignes sans reference d'appel | correspondance par montant et date |
| des reglements d'un montant different de l'appel | statut `ecart` |
| des mouvements inattribuables | statut `non_trouve` |
| des virements sur des produits dont l'encaissement n'est pas delegue | refus d'acte non delegue |

Tout est deterministe a graine fixe. L'empreinte SHA-256 de chaque fichier produit est inscrite au
manifeste.

## Le rapport de detection, et comment le lire

Le manifeste liste chaque anomalie **injectee**. Le rapport compare les deux ensembles sur le triplet
nom de fichier, code d'anomalie, reference de ligne, et publie le rappel et la precision reellement
calcules. Les valeurs mesurees sont dans `results/flux_rapport_detection.json`.

Deux precautions de lecture, qui valent plus que les chiffres eux-memes.

**Le rappel est la mesure utile pour les dix controles.** Il repond a la question posee : ce que le
generateur a plante, les controles l'ont-ils retrouve ?

**La precision ne se lit pas de la meme facon pour les controles bloquants et pour les avertissements.**
Les huit controles bloquants sont deterministes : une condition est remplie ou elle ne l'est pas, et un
faux positif y serait un defaut grave, puisqu'il rejetterait un lot sain. Les deux controles non
bloquants sont des jugements statistiques, et le portefeuille lui-meme contient des lignes qui
satisfont leur definition sans avoir ete injectees. Elles comptent donc comme faux positifs, et la
precision globale s'en trouve abaissee. Les masquer donnerait une precision de un, et une mesure sans
valeur.

C'est particulierement net pour la prestation proche du plafond. Dans ce portefeuille, la consommation
annuelle de nombreux adherents atteint reellement le seuil d'alerte de leur garantie, sans qu'aucune
anomalie n'ait ete injectee sur eux. Le controle a d'ailleurs ete corrige en cours de route : sa
premiere version signalait **toute** prestation d'un adherent deja au-dela du seuil, et la mesure a
montre qu'elle produisait dix fois plus de signalements que d'anomalies injectees. Un gestionnaire qui
recoit dix alertes pour un meme adherent n'en lit aucune. Le controle ne se declenche donc plus que sur
la prestation qui fait **franchir** le seuil : une alerte par adherent, par garantie et par annee, au
moment ou elle est actionnable.

Deux autres defauts ont ete trouves par la mesure et non par la relecture, et ils meritent d'etre cites
parce qu'ils auraient fausse les chiffres :

- le controle du total comparait la ligne de total a une somme **incomplete** quand une ligne du fichier
  etait illisible, et fabriquait ainsi une seconde anomalie a partir de la premiere ;
- le controle du plafond cumulait la consommation de **l'annee entiere**, y compris les prestations
  posterieures a celle qu'il examinait. Il regardait donc l'avenir, et signalait en juillet un
  depassement qui n'arriverait qu'en decembre.

## Les preuves, et ou les lire

Toute valeur publiee vient de l'un de ces fichiers. Aucun chiffre de cette documentation n'est recopie a
la main.

| Preuve | Fichier |
| --- | --- |
| fichiers recus produits, et leurs empreintes | `results/flux_generation.json` |
| sortie complete de `dbt build` | `results/dbt_build.txt` |
| journal d'execution par lot | `results/flux_journal_lots.json` |
| rapport de detection, rappel et precision | `results/flux_rapport_detection.json` |
| rejet integral d'un lot, lignes avant et apres | `results/flux_rejet_integral.json` |
| idempotence, empreinte de l'etat avant et apres | `results/flux_idempotence.json` |
| rapprochement, par statut et par methode | `results/flux_rapprochement.json` |
| commissions et retrocessions, et appels ecartes | `results/flux_commissions.json` |
| bordereaux produits | `results/flux_bordereaux.json` |
| empreinte memoire de la pile complete | `docs/DECISIONS.md`, section du dimensionnement |

## Comment rejouer la chaine

Sans Docker, sur SQLite, pour developper et tester vite :

```bash
make installer
make regenerer                 # schema et jeu de demonstration du module 1
python -m uv run courtage flux generer
python -m uv run courtage flux chaine
python -m uv run courtage flux rapport
python -m uv run python scripts/preuve_flux.py
```

Avec Docker, comme en production, graphe Airflow compris :

```bash
docker compose up -d --build   # PostgreSQL, ERP, fichiers recus, Airflow
# interface Airflow : http://localhost:8080
docker compose exec airflow-scheduler airflow dags unpause courtage_flux_financiers
docker compose exec airflow-scheduler airflow dags trigger courtage_flux_financiers
docker compose run --rm dbt docs generate
```

Pour lire la documentation dbt et le lineage, apres `dbt docs generate` :

```bash
python -m uv run dbt docs serve --project-dir dbt --profiles-dir dbt --target-path cible
```
