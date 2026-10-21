La délégation de gestion se modélise en trois tables, et c'est la liste des actes qui fait foi, jamais le libellé de portée.

# Modéliser la délégation de gestion d'un courtier délégataire

## Pourquoi cela ne peut pas être un drapeau

Un courtier **délégataire** accomplit, au nom de la compagnie, des actes qui appartiennent normalement à
l'assureur : émettre les appels de cotisation, encaisser, affilier et radier des adhérents, régler les
prestations, parfois instruire les sinistres.

Le premier réflexe est de poser un booléen « délégataire » sur la compagnie. Il ne tient pas trois
minutes face au métier : le périmètre varie d'un produit à l'autre chez la même compagnie, et il varie
dans le temps, parce qu'une convention a une date de début et parfois une date de fin.

## Les trois tables

| Table | Ce qu'elle porte |
| --- | --- |
| `convention_delegation` | l'accord avec une compagnie, ses dates de validité, sa portée déclarée |
| `convention_produit` | les produits que la convention couvre |
| `acte_delegue` | les actes que la convention autorise, un par ligne |

## Les trois décisions qui comptent

**La présence d'une ligne vaut autorisation, son absence vaut refus.** Pas de colonne `autorise`
booléenne dans `acte_delegue` : une ligne à `false` et une ligne absente auraient alors le même sens, et
deux façons de dire la même chose finissent toujours par diverger.

**La portée déclarée n'autorise rien.** Une convention saisie « totale » mais sans ligne pour les
prestations ne permet pas de régler une prestation. Le libellé sert à l'affichage, la liste des actes
seule fait foi. Sans cette règle, une convention mal saisie élargirait un périmètre réel, ce qui est
exactement ce qu'un contrôle de compagnie cherche.

**Aucune autorisation par défaut.** Un produit sans convention en vigueur ne permet aucun acte délégué.
L'inverse, autoriser tant que rien n'interdit, est ce qui produit les incidents : une convention oubliée
lors d'une reprise de données laisserait passer des actes que la compagnie n'a jamais délégués, et
l'anomalie ne se découvrirait qu'au contrôle.

## Ce que la base ne sait pas exprimer

Deux conventions ne doivent pas couvrir le même produit à la même date, sinon le périmètre devient
ambigu. Aucune base relationnelle ne sait exprimer « pas deux périodes de validité qui se chevauchent »
de façon portable. Le contrôle est donc fait dans le code, et il est **bloquant** : deviner laquelle des
deux conventions s'applique serait pire que de s'arrêter.

## Où placer la vérification

Avant l'écriture, dans le service, et jamais après. Le refus doit empêcher l'écriture, pas la constater.
Dans le projet, l'ordre est toujours le même : délégation, puis cycle de vie, puis cohérence des dates,
puis écriture.

L'interface en tire parti : quand un acte n'est pas délégué, le bouton est désactivé **et** la raison est
affichée. Laisser le bouton actif pour refuser ensuite ferait perdre une saisie ; masquer le bouton sans
rien dire laisserait croire à un défaut du logiciel.

## Ce qu'il faut en retenir

C'est le détail qu'un éditeur de logiciel de courtage repère immédiatement, et qu'un projet d'école ne
contient jamais. Il ne coûte que trois tables et une fonction de vérification, mais il change la nature
de ce qui est démontré : on ne modélise plus un portefeuille de contrats, on modélise le mandat sous
lequel ce portefeuille est géré.
