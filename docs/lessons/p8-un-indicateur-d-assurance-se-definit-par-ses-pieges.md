Chaque indicateur d'assurance a une version fausse qui se calcule aussi facilement que la bonne ; les chiffrer côte à côte dans le jeu de données montre ce que le piège coûte, et l'un d'eux a révélé un défaut du générateur.

# Définir un indicateur par ses pièges, chiffres à l'appui

- **Méthode.** Pour chaque indicateur de `docs/kpi.md`, une seconde requête (`sql/kpi/*b_*_pieges.sql`) calcule les
  variantes fausses sur les mêmes données. Ainsi, « sur cotisations émises au lieu d'acquises » n'est pas une mise en
  garde abstraite : c'est 133,27 % contre 121,18 % en 2026. Et les mesures de contrôle sont dans le modèle Power BI, pour
  que le tableau de bord le montre lui-même.
- **Le périmètre de délégation est un piège de première importance.** Les produits de prévoyance ont des cotisations et
  aucune prestation chez le cabinet : le ratio de tous les produits est de 109,67 % en 2025, contre 152,96 % sur le
  périmètre où le cabinet règle les prestations. Le périmètre se lit dans les conventions (`dim_produit`), pas dans une
  liste de produits écrite en dur.
- **Un stock se lit à une date.** La somme des douze clichés de 2025 donne 41 542 contrats pour un portefeuille de 3 704.
  Le modèle impose la lecture d'un cliché, et un test dbt vérifie l'identité stock et flux : effectif de fin égal à
  l'effectif de début plus les entrées moins les sorties, mois par mois.
- **Un piège défini peut ne pas se produire.** Aucune résiliation de contrat né dans la même période n'existe sur ce jeu :
  la règle de cohorte ne change rien aujourd'hui. Le dire, au lieu d'annoncer un effet qui n'est pas mesuré.
- **Un indicateur correct peut révéler une donnée irréaliste.** Le ratio sinistres sur primes dépasse 100 % sur toutes les
  périodes, parce que le générateur tire les prestations par tranche d'âge sans lien avec les cotisations. Le
  consigner comme limite ouverte plutôt que d'ajuster l'indicateur pour qu'il paraisse plausible.
- **Ne pas lire avant le début du quittancement.** Le premier appel est du 01/10/2023 : le ratio de 2023 vaut environ
  802 %, un artefact. Le rapport Power BI porte un filtre `annee >= 2024`.
