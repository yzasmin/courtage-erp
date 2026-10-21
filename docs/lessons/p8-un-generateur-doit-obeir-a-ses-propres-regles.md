Le générateur écrivait des données que l'API aurait refusées, et le test censé le détecter ne regardait que 200 lignes sur 5 777.

# Un générateur doit obéir aux règles que le service applique

## Le constat

Trois règles étaient écrites dans le service, donc appliquées à toute saisie par l'API et par
l'interface. Le générateur, lui, écrivait directement en base par insertion en lot, sans passer par le
service. Résultat, mesuré sur le jeu de démonstration :

| Anomalie | Lignes concernées |
| --- | --- |
| Contrats dont les avenants reculent dans le temps | 46 |
| Contrats dont le cache diffère de la reconstitution | 40 |
| Appels déclarés encaissés sans aucune ligne d'encaissement | 28 338 |
| Prestations servies après la résiliation du contrat | 137 |
| Appels surfacturés d'un mois à la résiliation | 202 |

Chacune de ces lignes aurait été refusée si elle était passée par l'API.

## Les trois causes

**Les dates étaient tirées indépendamment les unes des autres.** Changement de formule à plus un à dix
mois, changement d'apporteur à plus un à onze, suspension à plus deux à huit, tous comptés depuis la
même échéance, puis numérotés dans l'ordre du code et non dans l'ordre des dates. Un avenant de rang 5
pouvait donc précéder un avenant de rang 4.

**L'état était modifié avant d'être validé.** La formule et l'apporteur étaient remplacés, puis la date
était testée. Quand la date tombait hors période, l'avenant n'était pas écrit, mais les avenants
suivants portaient quand même la nouvelle valeur, que plus aucun acte n'expliquait.

**Une règle métier était réimplémentée à la main.** Le générateur décidait lui-même quels flux produire
selon la délégation, au lieu d'interroger `domaine.delegation`. Les deux implémentations ont divergé :
le statut de l'appel était tiré au sort avant de savoir si l'encaissement était seulement possible.

## Les correctifs

1. **L'invariant est tenu par l'émetteur, pas par les appelants.** La fonction qui écrit un avenant
   refuse une date antérieure au dernier avenant émis, et lève. Un générateur qui produit des données
   invalides est pire qu'un générateur qui s'arrête.
2. **La date est arrêtée avant toute mutation.** Si l'avenant ne peut pas être émis, l'état du contrat
   ne bouge pas.
3. **Un test confronte les deux implémentations** sur les données réelles : zéro appel sur un produit
   dont le quittancement n'est pas délégué, zéro prestation sur un produit dont la gestion ne l'est pas,
   zéro appel encaissé sans ligne d'encaissement.

## Le test qui ne servait à rien

Le test censé attraper la deuxième anomalie existait. Il faisait :

```python
contrats = list(session.scalars(select(Contrat).limit(200)))
```

Sa docstring annonçait « les 5 778 contrats ». Il en regardait 200, sans ordre, et dans la configuration
par défaut la base ne contenait aucun contrat : la boucle ne s'exécutait jamais et le test passait sans
exécuter une seule assertion.

Corrigé : parcours complet et ordonné, `skip` explicite quand la base est vide plutôt qu'une boucle
muette, et comparaison de cinq champs au lieu de trois.

## Ce qu'il faut en retenir

Un générateur de données de démonstration n'est pas un script annexe : c'est un deuxième chemin
d'écriture vers la même base. Il doit respecter les mêmes invariants que le premier, et quelque chose
doit le vérifier.

Et une boucle de test sans garde-fou est un test qui passe à vide. Quand un test parcourt une
collection, il doit refuser de passer si la collection est vide.
