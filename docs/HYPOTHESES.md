Toute valeur métier simulée du projet, avec sa justification et son statut. Aucune n'est un barème réel.

# Hypothèses de simulation

## Règle qui gouverne ce fichier

Le cabinet modélisé n'existe pas, ses compagnies n'existent pas, ses adhérents n'existent pas. Chaque
valeur numérique qui ressemble à un paramètre d'assurance est une **hypothèse de simulation** : elle sert
à produire des données cohérentes, elle ne reproduit aucun barème légal, aucun tarif de marché et aucun
accord commercial réel.

Conséquence pratique, appliquée partout dans le dépôt : ces valeurs ne sont jamais écrites en dur dans le
code métier. Elles sont stockées en base, avec des dates de validité, et modifiables sans toucher au code.
Un lecteur du métier peut donc les remplacer par les siennes.

Statut possible d'une valeur :

- **hypothèse** : choisie pour la simulation, ni mesurée ni vérifiée contre une source externe.
- **mesuré** : constaté par une exécution enregistrée dans `results/` ou `docs/`.

À ce stade du projet, toutes les valeurs de ce fichier sont des hypothèses. Les valeurs mesurées sont dans
`results/` et dans `docs/PROGRESS.md`.

## Volumétrie du portefeuille simulé

La spécification fixe ces ordres de grandeur. Ils donnent un cabinet de taille moyenne, assez gros pour
que les indicateurs aient du sens et assez petit pour tourner sur un poste de 8 Go.

| Paramètre | Valeur | Statut |
| --- | --- | --- |
| Adhérents | environ 5 000 | hypothèse, fixée par la spécification |
| Entreprises souscriptrices | 40 | hypothèse, fixée par la spécification |
| Compagnies | 3 | hypothèse, fixée par la spécification |
| Produits | 8 | hypothèse, fixée par la spécification |
| Apporteurs | 10 | hypothèse, fixée par la spécification |
| Profondeur d'historique | 3 ans | hypothèse, fixée par la spécification |
| Graine du générateur | 20261019 | convention du projet, rend la génération reproductible |

## Taxes sur les cotisations

Les contrats d'assurance de personnes relèvent en France d'une taxation qui dépend de la nature du
contrat. Le projet stocke un taux par branche dans la table `taux_taxe`, avec des dates de validité, et
applique le taux en vigueur à la date d'échéance.

**Correction d'une affirmation antérieure.** Ce document a d'abord présenté ces trois taux comme
entièrement inventés, ce qui était inexact pour le premier d'entre eux. La table ci-dessous dit
maintenant, pour chacun, d'où il vient.

| Branche | Taux retenu | Statut |
| --- | --- | --- |
| Santé individuelle | 13,27 % | **taux réel repris tel quel** : c'est le taux de la taxe de solidarité additionnelle appliqué aux contrats de complémentaire santé. Il n'est pas inventé, et le présenter comme tel serait malhonnête. |
| Santé collective | 13,27 % | même taux que ci-dessus, appliqué ici à toutes les affiliations sans distinction |
| Prévoyance | 9,00 % | **hypothèse de simulation** : la taxation de la prévoyance varie selon la garantie et le caractère obligatoire ou facultatif du contrat, et ce taux unique n'en reproduit aucun en particulier |

Trois réserves, pour que personne ne prenne ce tableau pour un barème opposable :

1. **La distinction qui détermine le taux réel n'est pas modélisée.** En santé, le taux dépend du
   caractère solidaire et responsable du contrat, notion que le projet ne porte pas. Tous les contrats
   santé sont donc taxés au même taux, ce qu'un vrai portefeuille ne fait pas.
2. **Aucune exonération n'est traitée**, alors qu'il en existe.
3. **Le taux n'est pas daté dans le jeu de démonstration** : une seule période de validité couvre tout
   l'historique. Ce qui est démontré est le mécanisme, à savoir que le calcul va chercher le taux en
   vigueur à la date d'échéance, et non la justesse d'un barème.

Autrement dit, le taux de la santé est juste, le reste du dispositif fiscal ne l'est pas, et le projet ne
prétend pas calculer une taxe réellement exigible.

Ce qui est démontré ici n'est pas la justesse du taux : c'est que le taux est un paramètre daté, que le
calcul va le chercher en base à la date de l'échéance, et qu'un changement de taux au 1er janvier se
répercute sans toucher au code.

## Commissions reçues des compagnies

Le cabinet est un courtier grossiste : la compagnie lui verse une commission sur les cotisations, et le
cabinet en reverse une part à l'apporteur qui a amené l'affaire.

| Paramètre | Valeur | Statut |
| --- | --- | --- |
| Taux de commission, santé individuelle | 12 % à 18 % selon le produit | hypothèse de simulation |
| Taux de commission, santé collective | 8 % à 12 % selon le produit | hypothèse de simulation |
| Taux de commission, prévoyance | 15 % à 22 % selon le produit | hypothèse de simulation |
| Assiette de la commission | cotisation encaissée, hors taxe | hypothèse de simulation, paramétrable en base |
| Date du taux appliqué | taux en vigueur à la date d'échéance de l'appel de cotisation | règle de calcul du projet |

Le choix de l'assiette mérite une phrase, parce qu'il change les chiffres. Deux pratiques coexistent dans
le métier : commissionner sur la cotisation **appelée**, ou sur la cotisation **encaissée**. Le projet
retient l'encaissée, qui est la plus prudente pour le cabinet, et en fait un paramètre de la table
`taux_commission` afin que l'autre pratique soit représentable sans modifier le code.

## Rétrocessions aux apporteurs

| Paramètre | Valeur | Statut |
| --- | --- | --- |
| Part de la commission reversée, mandataire | 50 % à 70 % | hypothèse de simulation |
| Part de la commission reversée, sous-courtier | 60 % à 80 % | hypothèse de simulation |
| Part de la commission reversée, comparateur | 30 % à 45 % | hypothèse de simulation |
| Part de la commission reversée, production directe | 0 % | hypothèse de simulation : une affaire arrivée sans intermédiaire n'a personne à rémunérer. Le type d'apporteur s'appelait « salarié », ce qui était un contresens : un salarié du cabinet n'est pas un apporteur, il n'a ni mandat ni immatriculation ORIAS. |

## Tarifs et revalorisations

| Paramètre | Valeur | Statut |
| --- | --- | --- |
| Cotisation mensuelle, santé individuelle | 35 à 180 euros selon la formule et l'âge | hypothèse de simulation |
| Cotisation mensuelle, santé collective | 28 à 95 euros par salarié adhérent | hypothèse de simulation |
| Cotisation mensuelle, prévoyance | 12 à 70 euros | hypothèse de simulation |
| Date des revalorisations | 1er janvier, échéance commune du portefeuille | hypothèse de simulation |
| Ampleur des revalorisations | 2 % à 9 % selon l'année et le produit | hypothèse de simulation |
| Majoration liée à l'âge | par tranche de cinq ans | hypothèse de simulation |

## Résiliations

Le générateur n'injecte pas des résiliations au hasard : il leur donne des causes, pour que le module 5
ait quelque chose à apprendre. Les causes et leur poids sont des hypothèses.

| Facteur de résiliation | Effet retenu | Statut |
| --- | --- | --- |
| Revalorisation tarifaire supérieure à 6 % | augmente nettement la probabilité de résiliation à l'échéance suivante | hypothèse de simulation |
| Ancienneté inférieure à 18 mois | augmente la probabilité de résiliation | hypothèse de simulation |
| Sinistralité individuelle très faible | augmente la probabilité de résiliation : l'adhérent ne voit pas le retour de sa cotisation | hypothèse de simulation |
| Sinistralité individuelle très forte | diminue la probabilité de résiliation | hypothèse de simulation |
| Apporteur | deux apporteurs sur dix portent un portefeuille plus volatil | hypothèse de simulation |
| Âge supérieur à 60 ans | diminue la probabilité de résiliation | hypothèse de simulation |
| Taux de résiliation annuel visé | environ 8 % à 12 % du portefeuille | hypothèse de simulation |

Les motifs de résiliation employés dans le modèle de données sont du vocabulaire métier, pas des valeurs
numériques : résiliation à l'échéance, résiliation infra-annuelle, non-paiement après mise en demeure,
changement de situation, décès, résiliation par la compagnie, transfert de portefeuille. Le préavis
associé à la résiliation à l'échéance est un paramètre de simulation fixé à deux mois, et non une règle
légale affirmée.

## Prestations

| Paramètre | Valeur | Statut |
| --- | --- | --- |
| Nombre de prestations par adhérent et par an | 0 à 14 selon l'âge et la formule | hypothèse de simulation |
| Montant des demandes | calibré sur la cotisation courue de chaque contrat, avec une échelle par branche (santé individuelle 1,42, santé collective 1,62) et un multiplicateur de consommation à queue lourde (55 % de petits, 35 % de moyens, 10 % de gros consommateurs) | hypothèse de simulation, mesurée pour que le ratio sinistres sur primes publié tombe entre 70 et 85 % sur les exercices complets |
| Saisonnalité | creux en juillet et en août, pic en novembre, décembre et janvier | hypothèse de simulation, calquée sur un rythme de consommation de soins plausible |
| Postes de garantie simulés | soins courants, hospitalisation, optique, dentaire, audiologie, décès, incapacité, invalidité | vocabulaire métier, pas une valeur numérique |
| Plafonds annuels par garantie et par formule | 150 à 2 000 euros selon le poste et le niveau | hypothèse de simulation |
| Délai entre la date des soins et le règlement | 2 à 30 jours | hypothèse de simulation |

## Anomalies injectées, pour le module 2

| Paramètre | Valeur | Statut |
| --- | --- | --- |
| Part de lignes anormales dans les fichiers reçus | 3 % à 5 % | hypothèse, fixée par la spécification |

La nature exacte des anomalies et leur manifeste de vérité terrain seront définis au module 2.

## Santé collective

| Paramètre | Valeur | Statut |
| --- | --- | --- |
| Polices collectives | une par entreprise souscriptrice, soit 40 | hypothèse de simulation |
| Périodicité des appels groupés | trimestrielle dans la majorité des cas | hypothèse de simulation, calquée sur l'usage d'un service comptable |
| Formule socle de la police | niveau 1 ou 2, l'affilié pouvant souscrire au-dessus | hypothèse de simulation |
| Moyen de règlement d'une entreprise | virement | hypothèse de simulation |

**Simplification assumée : le prorata temporis n'est pas traité.** Un salarié affilié en cours de
période est compté pour la période entière dans l'appel groupé. Dans la réalité, la cotisation du mois
d'entrée et celle du mois de sortie se calculent au prorata, selon des règles qui varient d'une
convention à l'autre. Le reproduire n'ajouterait rien à ce que le projet démontre, et le passer sous
silence aurait été malhonnête.

**Simplification assumée : la police ne porte pas de tarif.** Le tarif se lit sur chaque affiliation,
parce qu'il dépend de la formule et de l'âge du salarié. Une police réelle porte en plus une répartition
entre part patronale et part salariale, que le projet ne modélise pas.
