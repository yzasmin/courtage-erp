Un moteur d'inspection laissé ouvert bloque le DROP TABLE suivant sur PostgreSQL, sans message d'erreur ni délai d'attente.

# Une connexion d'inspection oubliée bloque les migrations sur PostgreSQL

## Le symptôme

Un script qui monte les migrations, lit la liste des tables, les redescend, puis les remonte. Il passe en
une seconde sur SQLite. Sur PostgreSQL, il se fige après la première révision et ne rend jamais la main.
Aucun message, aucune exception, aucun délai d'attente. La base montre bien les 21 tables de la première
révision, et personne ne voit de requête bloquée au moment où on la regarde.

## La cause

Le script gardait un moteur SQLAlchemy ouvert pour inspecter le schéma entre deux migrations :

```python
moteur = cree_moteur()
...
tables = set(inspect(moteur).get_table_names())   # laisse une connexion dans la reserve
```

La connexion revient dans la réserve du moteur, mais elle détient encore un verrou de lecture sur les
tables qu'elle vient de lire. Le `DROP TABLE` de la migration suivante attend que ce verrou se libère,
et il attend indéfiniment, parce que personne ne ferme le moteur.

SQLite ne s'en aperçoit pas : il n'a pas ce modèle de verrous. Le défaut passe donc inaperçu en local et
ne se manifeste que sur la base de production.

## Le correctif

Chaque inspection crée son moteur, lit, et le libère.

```python
def _tables_presentes() -> set[str]:
    moteur = cree_moteur(echo=False)
    try:
        return set(inspect(moteur).get_table_names())
    finally:
        moteur.dispose()
```

Quelques centièmes de seconde de coût, et le script ne peut plus se bloquer lui-même.

## Ce qu'il faut en retenir

Tout ce qui exécute du DDL doit être seul sur la base. Une connexion de lecture laissée ouverte, même
inactive, suffit à bloquer une migration sur PostgreSQL. Et un script qui se fige sans message, sur un
moteur qui a des verrous et pas sur un moteur qui n'en a pas, oriente vers un verrou plutôt que vers une
erreur de logique.
