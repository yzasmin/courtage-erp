La documentation décrivait un appel de cotisation adressé à l'entreprise, le schéma en adressait un à chaque salarié : c'est le schéma qui avait tort.

# Quand la documentation et le schéma ne décrivent pas le même métier

## Le constat

La documentation du modèle affirmait, noir sur blanc : « en collectif, l'entreprise est le souscripteur
et le salarié est l'adhérent. La cotisation est appelée auprès de l'entreprise, les prestations sont
servies au salarié. »

Le schéma, lui, donnait un contrat par salarié et un appel de cotisation par salarié. Il n'y avait ni
police, ni payeur, ni appel groupé. 2 382 contrats collectifs pour 40 entreprises, et 2 382 appels
mensuels adressés à personne en particulier.

Les deux textes étaient cohérents chacun de leur côté. Ils ne parlaient simplement pas du même métier.

## Pourquoi personne ne l'avait vu

Tous les tests passaient. Toutes les preuves étaient vertes. Les migrations montaient et descendaient,
la génération était reproductible, l'empreinte était identique sur les deux moteurs.

C'est précisément le piège : **la rigueur technique ne détecte pas une erreur de domaine.** On peut
vérifier avec une grande précision un modèle qui décrit le mauvais métier. Aucun test unitaire ne
demande « est-ce ainsi que cela se passe dans la vraie vie ».

Ce qui l'a trouvé, c'est une relecture par quelqu'un qui connaissait le métier et qui a ouvert un
dossier collectif en se demandant qui payait.

## Ce qu'il a fallu ajouter

| Objet | Rôle |
| --- | --- |
| `police_collective` | le contrat cadre signé par l'entreprise |
| `contrat.police_id` | l'affiliation du salarié à cette police |
| `appel_cotisation.police_id` | l'appel groupé, adressé à l'entreprise |
| `ligne_appel_cotisation` | la part de chaque affilié dans cet appel |

Et la règle qui va avec : un appel s'adresse à un contrat **ou** à une police, jamais aux deux, jamais à
aucun, imposée par une contrainte de vérification.

## Les effets de bord, qui sont le vrai coût

Changer un objet central ne se limite jamais à ajouter une table.

- L'empreinte du jeu de données change, donc toutes les preuves sont à republier.
- La fiche contrat affichait un total de zéro euro juste au-dessus d'un tableau d'appels bien rempli,
  parce que les totaux ne sommaient que `contrat_id`.
- La revision qui rend `contrat_id` facultatif **ne peut plus redescendre** une fois des appels groupés
  enregistrés : le schéma précédent ne sait pas représenter un appel sans contrat. C'est une propriété
  de la migration, pas un défaut, mais il faut la connaître et l'écrire.
- Un test de délégation jugeait les flux à une date unique, alors qu'une convention expire : un appel
  émis avant l'expiration est régulier, et le juger après le déclarait à tort irrégulier.

## Ce qu'il faut en retenir

Deux choses.

**Faire relire le domaine par quelqu'un qui le connaît, tôt.** Les tests prouvent qu'un code fait ce
qu'on lui a demandé ; ils ne disent rien sur la pertinence de la demande. Sur un sujet métier, c'est la
relecture humaine qui trouve les vraies erreurs, et elle coûte beaucoup moins cher avant qu'après.

**Traiter un écart entre la documentation et le code comme un défaut, pas comme une imprécision.**
Quand les deux divergent, l'un des deux a tort, et ce n'est pas toujours la documentation. Ici c'était
le schéma. L'écart était visible depuis le début : il suffisait de lire les deux côte à côte.
