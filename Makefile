# Raccourcis du projet. `make aide` liste tout.
#
# Deux chemins possibles, qui executent le meme code :
#   - sans Docker, sur SQLite : installer, migrer, generer, tests, servir ;
#   - avec Docker, sur PostgreSQL : pile, puis preuve-postgres.
SHELL := /bin/bash

# Adresse de la base PostgreSQL du compose, vue depuis le poste. Sert aux preuves lancees en local
# contre la base du conteneur, sans entrer dans le conteneur.
POSTGRES_LOCAL ?= postgresql+psycopg://courtage:courtage@localhost:5432/courtage
GRAINE ?= 20261019
ADRESSE ?= http://127.0.0.1:8000

.PHONY: aide installer migrer demigrer generer regenerer empreinte tests tests-demonstration style \
        servir pile arret journaux etat preuve-migrations preuve-reproductibilite preuve-postgres \
        preuve-api preuve-coherence preuve-contraintes preuve-mutation preuves capture nettoyer

aide: ## Liste les commandes
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# --- Sans Docker, sur SQLite -------------------------------------------------------------------

installer: ## Installe l'environnement Python (uv)
	python -m uv sync --frozen

migrer: ## Monte le schema jusqu'a la derniere revision
	python -m uv run courtage migrer

demigrer: ## Redescend tout le schema (destructif : supprime les tables et leurs donnees)
	python -m uv run courtage migrer --vers base

generer: ## Genere le jeu de demonstration, si la base est vide
	python -m uv run courtage generer --si-vide

regenerer: ## Repart de zero : redescend le schema, le remonte, regenere
	python -m uv run courtage migrer --vers base
	python -m uv run courtage migrer
	python -m uv run courtage generer

empreinte: ## Calcule l'empreinte SHA-256 du jeu de donnees
	python -m uv run courtage empreinte

tests: ## Tests unitaires, sur une base temporaire jetable
	python -m uv run pytest -q

tests-demonstration: ## Rejoue la suite contre la base de demonstration, ce qui active les tests de signaux
	COURTAGE_BASE_URL="sqlite+pysqlite:///$$(pwd -W 2>/dev/null || pwd)/courtage.db" python -m uv run pytest -q

style: ## Verification de style
	python -m uv run ruff check src tests scripts

servir: ## Demarre l'API et l'interface sur http://127.0.0.1:8000
	python -m uv run courtage servir

# --- Avec Docker, sur PostgreSQL ----------------------------------------------------------------

pile: ## Monte la pile complete (PostgreSQL, migrations, generation, application)
	docker compose up -d --build

arret: ## Arrete la pile sans supprimer les volumes
	docker compose down

journaux: ## Affiche les journaux de la pile
	docker compose logs --tail 80

etat: ## Etat des conteneurs et empreinte memoire reelle
	docker compose ps
	docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}'

# --- Preuves ------------------------------------------------------------------------------------

preuve-migrations: ## Prouve que les migrations montent et redescendent, sur la base courante
	python -m uv run python scripts/preuve_migrations.py

preuve-reproductibilite: ## Prouve que deux generations de meme graine donnent la meme empreinte
	python -m uv run python scripts/preuve_reproductibilite.py --graine $(GRAINE)

preuve-postgres: ## Rejoue migrations, generation, coherence et tests sur la base PostgreSQL du compose
	COURTAGE_BASE_URL="$(POSTGRES_LOCAL)" python -m uv run python scripts/preuve_migrations.py
	COURTAGE_BASE_URL="$(POSTGRES_LOCAL)" python -m uv run python scripts/preuve_reproductibilite.py --graine $(GRAINE)
	COURTAGE_BASE_URL="$(POSTGRES_LOCAL)" python -m uv run python scripts/preuve_coherence_metier.py
	COURTAGE_BASE_URL="$(POSTGRES_LOCAL)" python -m uv run python scripts/preuve_contraintes.py
	COURTAGE_BASE_URL="$(POSTGRES_LOCAL)" python -m uv run pytest -q

preuve-api: ## Enregistre une transcription des comportements cles de l'API (application demarree)
	python -m uv run python scripts/preuve_api.py --adresse $(ADRESSE)

preuve-coherence: ## Controle la coherence metier des donnees generees
	python -m uv run python scripts/preuve_coherence_metier.py

preuve-contraintes: ## Prouve que la base refuse les ecritures interdites, en SQL direct
	python -m uv run python scripts/preuve_contraintes.py

preuve-mutation: ## Verifie que les tests detectent les defauts qu'ils pretendent couvrir
	python -m uv run python scripts/preuve_mutation.py

preuves: ## Enchaine toutes les preuves du module 1 sur SQLite
	python -m uv run python scripts/preuve_migrations.py
	python -m uv run python scripts/preuve_reproductibilite.py --graine $(GRAINE)
	python -m uv run python scripts/preuve_coherence_metier.py
	python -m uv run python scripts/preuve_contraintes.py
	python -m uv run python scripts/preuve_mutation.py
	python -m uv run pytest -q

capture: ## Capture les ecrans de l'interface dans docs/captures/
	python -m uv run python scripts/captures.py

nettoyer: ## Supprime la pile Docker et ses volumes (destructif)
	docker compose down -v
