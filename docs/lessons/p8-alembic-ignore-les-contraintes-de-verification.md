Alembic n'autogénère pas les `CheckConstraint` : une règle ajoutée au modèle doit être écrite à la main dans la migration, et prouvée par une écriture refusée.

# Alembic ignore les contraintes de vérification

## Ce qui s'est passé

Trois règles ont été déclarées dans le modèle SQLAlchemy par la révision 0003 :
`ck_appel_cotisation_destinataire_unique`, `ck_appel_cotisation_au_moins_un_affilie` et
`ck_commission_destinataire_unique`. La migration a été produite par `alembic revision --autogenerate`.
Aucune des trois n'a été émise en base. Elles y sont restées absentes pendant deux révisions.

## Pourquoi personne ne l'a vu

Deux garde-fous existaient, et tous les deux étaient aveugles au même endroit.

`alembic.autogenerate.compare_metadata` ne compare pas les contraintes de vérification. Ce n'est pas un
défaut d'Alembic : une expression SQL de contrainte n'est pas comparable de façon fiable entre un modèle
Python et un schéma réel, parce que le moteur la réécrit. Alembic préfère ne rien dire plutôt que de
proposer des migrations fantômes à chaque exécution.

Le test de non-dérive du schéma, `test_le_schema_migre_correspond_au_modele`, repose sur cette même
fonction. Il est donc resté vert. C'est le piège : un test qui se croit exhaustif et qui ne l'est pas
donne plus de fausse confiance que l'absence de test.

## Ce que ça coûtait

Un import ou un script de reprise pouvait écrire un appel de cotisation portant à la fois un contrat
individuel et une police collective. Cet appel aurait été quittancé deux fois.

## La règle retenue

Toute contrainte de vérification ajoutée au modèle s'écrit **à la main** dans la migration, et se prouve
par une écriture qui doit être refusée. Sur SQLite, l'ajout passe par
`op.batch_alter_table(...).create_check_constraint(...)`, qui reconstruit la table ; sur PostgreSQL c'est
un `ALTER TABLE ... ADD CONSTRAINT`. Le nom est donné nu, sans le préfixe `ck_<table>_` : la convention
de nommage du projet le pose, y compris sur `drop_constraint`.

La preuve vit dans `scripts/preuve_contraintes.py`. Elle écrit du SQL brut sur la connexion, donc hors de
toute validation SQLAlchemy, et exige non seulement un refus mais un message qui **nomme** la contrainte.
Sans cette dernière exigence, une violation refusée pour une autre raison, par exemple une clé étrangère
inexistante, passerait pour une preuve.
