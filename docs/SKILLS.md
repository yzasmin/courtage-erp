Les skills et agents à charger pour chaque module, avec leur nom exact dans cette installation. À suivre tel quel : les noms cités dans la spécification étaient approximatifs.

# Skills et agents, par module

Règle : charger le skill **avant** d'écrire le code du module, pas après. Si un skill nommé ici est
absent, continuer sans lui et le signaler une fois dans le rapport, comme le demande la spécification.

## Tout le long du projet

| Besoin | Nom exact |
| --- | --- |
| Conventions de code | `anthropic-skills:coding-standards` |
| Conteneurs et compose | `anthropic-skills:docker-patterns` |
| Sessions longues | `anthropic-skills:strategic-compact` |
| Revue de fin de module | `engineering:code-review` |
| Découpage en tâches vérifiables | `agent-skills:plan` |
| Implémentation incrémentale | `agent-skills:incremental-implementation` |

Agents de relecture, à lancer en fin de module sur le code écrit (ils rendent un avis, ils ne décident
pas) : `ecc:python-reviewer`, `ecc:code-reviewer`, `ecc:security-reviewer`, `ecc:silent-failure-hunter`,
`agent-skills:test-engineer`, `agent-skills:security-auditor`.

## Planification

`anthropic-skills:blueprint`, `engineering:architecture`, `engineering:system-design`,
`agent-skills:spec-driven-development`.

## Module 1, cœur ERP

| Besoin | Nom exact |
| --- | --- |
| Migrations versionnées | `anthropic-skills:database-migrations` |
| Conception de l'API | `anthropic-skills:api-design` puis `agent-skills:api-and-interface-design` |
| Structure du service | `anthropic-skills:backend-patterns` |
| Base PostgreSQL | `ecc:postgres-patterns` |
| Interface de gestionnaire | `ecc:frontend-patterns`, et `ecc:frontend-design-direction` pour la direction visuelle |
| Accessibilité de l'interface | `ecc:accessibility` |
| Tests pilotés par les cas | `agent-skills:test-driven-development` |

Si l'API est écrite avec FastAPI : `ecc:fastapi-patterns`, et l'agent `ecc:fastapi-reviewer` pour la
relecture.

## Module 2, flux financiers avec Airflow et dbt

| Besoin | Nom exact |
| --- | --- |
| Contrôles de qualité des données | `data:validate-data` |
| Requêtes SQL et modélisation | `data:sql-queries`, `data:write-query` |
| Stratégie de test | `engineering:testing-strategy` |
| Exploration des données produites | `data:explore-data` |
| Revue de la base et des requêtes | agent `ecc:database-reviewer` |

## Module 3, pilotage et Power BI

| Besoin | Nom exact |
| --- | --- |
| Construction du tableau de bord | `data:build-dashboard` |
| Règles de visualisation | `dataviz`, `data:data-visualization`, `data:create-viz` |
| Lecture métier des chiffres | `data:analyze` |

Rappel du portfolio : les leçons `p3-powerbi-pbip-tmdl.md` et `p3-powerbi-verifier-les-mesures.md` de
"Portfolio\site\docs\lessons\" décrivent déjà comment produire un projet PBIP en TMDL, l'ouvrir dans
Power BI Desktop et contrôler chaque mesure DAX contre le SQL. Les relire évite de refaire les erreurs.

## Module 4, intelligence artificielle métier

| Besoin | Nom exact |
| --- | --- |
| Maîtrise du coût et de la latence | `anthropic-skills:cost-aware-llm-pipeline` |
| Tests de non-régression des réponses | `anthropic-skills:ai-regression-testing` |
| Construction de la boucle d'outils | `anthropic-skills:agent-harness-construction` |
| Si un modèle distant est utilisé | `claude-api` |
| Revue du RAG du module 4b | agent `ecc:rag-pipeline-reviewer` |

Le RAG RE2020 de "Portfolio\projets-data\agent-ia-llm\" fournit le découpage, la recherche hybride et le
jeu d'évaluation par phrase attendue. Ses deux leçons les plus utiles : sur un corpus technique, la
recherche lexicale bat la recherche vectorielle, et un petit modèle local tient mal une boucle d'appel
d'outils, là où une chaîne directe fonctionne.

## Module 5, prédiction de résiliation

| Besoin | Nom exact |
| --- | --- |
| Démarche statistique | `data:statistical-analysis`, `statistical-analysis` |
| Modèles | `scikit-learn` |
| Explicabilité | `shap` |
| Revue de la démarche d'apprentissage | agent `ecc:mle-reviewer` |

## Module 6, documentation et page de presentation

| Besoin | Nom exact |
| --- | --- |
| Documentation technique | `engineering:documentation` |
| Rédaction de la fiche projet | `anthropic-skills:article-writing` |
| Style naturel, sans tics d'écriture | `anthropic-skills:humanizer` |
| Schémas Mermaid | `markdown-mermaid-writing` |
| Teaser vidéo de la fiche | `hyperframes`, puis le script `Portfolio\video\teaser-projet\render.sh` |
| Procédure d'exploitation | `operations:runbook` |

## Ce qui n'est pas pertinent ici

Les skills de vente, de marketing et de gestion de petite entreprise (`small-business:*`,
`ryze-marketing:*`) ne servent pas ce projet, malgré leur nombre. Les skills scientifiques
(bio-informatique, chimie, imagerie) non plus. Ne pas les charger.
