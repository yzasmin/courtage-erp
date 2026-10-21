Insérer en fournissant les identifiants ne fait pas avancer les séquences PostgreSQL : la première écriture par l'application échoue après la reprise de données.

# Recaler les séquences après une reprise de données

## Le problème

Le générateur attribue lui-même les identifiants, en partant de 1. C'est ce qui le rend déterministe et
rapide : il insère par lots, sans relire la base pour récupérer les clés.

Sur SQLite, cela ne pose aucun problème : une colonne `INTEGER PRIMARY KEY` repart de `max(rowid) + 1`.

Sur PostgreSQL, une insertion qui fournit explicitement la clé primaire **ne fait pas avancer la
séquence**. Après l'insertion de 5 382 adhérents, la séquence en est toujours à 1. La première
souscription saisie dans l'interface réclame donc l'identifiant 1, déjà pris, et échoue sur une
violation d'unicité.

Le symptôme apparaît **après** la reprise, jamais pendant, ce qui le rend difficile à relier à sa cause :
la reprise s'est bien passée, les chiffres sont bons, et c'est le premier utilisateur qui tombe dessus.

## Le correctif

Recaler chaque séquence au-delà du plus grand identifiant inséré, à la fin de la reprise.

```sql
SELECT setval(pg_get_serial_sequence('adherent', 'id'), (SELECT MAX(id) FROM adherent));
```

Dans le projet, `generateur.outils.recale_sequences` le fait pour les sept tables dont le générateur
attribue les identifiants, et ne fait rien quand le moteur n'est pas PostgreSQL. Le compte rendu de
génération affiche le nombre de séquences recalées, ce qui rend l'opération visible plutôt que
silencieuse. L'exécution du compose l'a confirmé : « sequences recalees : 7 ».

## Ce qu'il faut en retenir

C'est un classique de toute migration de données vers un ERP, pas une particularité de ce projet. Dès
qu'une reprise écrit des clés primaires explicites, prévoir le recalage des séquences dans la même
procédure, et le faire apparaître dans le compte rendu plutôt que de le supposer fait.
