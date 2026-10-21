Sur SQLite, le pilote pysqlite valide la transaction englobante au lieu de relâcher le point de reprise, ce qui fait fuir les données d'un test au suivant.

# Les points de reprise SQLite ne fonctionnent pas sans désactiver le pilote

## Le symptôme

Une suite de tests isolée par transaction : chaque test ouvre une connexion, démarre une transaction,
travaille dans une session liée à cette connexion avec `join_transaction_mode="create_savepoint"`, puis
annule tout à la fin. Les tests qui n'écrivent qu'à travers `session.flush()` passent. Dès qu'un test
passe par l'API, qui appelle `session.commit()`, le test **suivant** échoue sur une violation d'unicité,
alors qu'il n'a rien fait de faux.

## La cause

Le pilote `pysqlite` ouvre et valide les transactions tout seul, en devinant d'après le type de requête
qu'il voit passer. Le `SAVEPOINT` posé par SQLAlchemy ne se trouve donc pas dans la transaction que l'on
croit, et le `COMMIT` émis par le code testé valide la transaction englobante au lieu de relâcher
seulement le point de reprise. L'annulation de fin de test ne ramène alors plus rien.

Rien ne le signale : pas d'exception, pas d'avertissement. Seul le test suivant échoue, et sur un
symptôme sans rapport apparent avec la cause.

## Le correctif

Désactiver la gestion implicite du pilote et émettre soi-même le `BEGIN`. C'est ce que documente
SQLAlchemy pour ce pilote.

```python
@event.listens_for(moteur, "connect")
def _desactive_la_gestion_implicite(connexion_dbapi, _enregistrement):
    connexion_dbapi.isolation_level = None

@event.listens_for(moteur, "begin")
def _ouvre_la_transaction(connexion):
    connexion.exec_driver_sql("BEGIN")
```

Appliqué au moteur **de test** seulement, dans `tests/conftest.py`, pour ne rien changer au comportement
du code livré. Les neuf tests en erreur sont passés au vert d'un coup.

## Ce qu'il faut en retenir

Quand des tests isolés par transaction se polluent entre eux sur SQLite, ne pas chercher d'abord dans le
code testé : vérifier le mode de transaction du pilote. Et se méfier d'une suite qui passe test par test
mais échoue en bloc, ou l'inverse : c'est presque toujours un problème d'isolation, pas de logique.
