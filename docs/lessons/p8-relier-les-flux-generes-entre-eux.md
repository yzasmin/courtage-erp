Des prestations tirées sans rapport avec les cotisations donnaient un ratio sinistres sur primes de 177 % ; calibrées sur la cotisation de chaque contrat, avec une consommation à queue lourde, elles donnent 76 à 81 % sur les exercices complets.

# Relier les flux générés entre eux

- **Constat.** Le premier indicateur du module 3 a révélé que le générateur de données ne reliait pas ses flux : le nombre de
  prestations dépendait de la tranche d'âge, leur montant de la garantie, la cotisation du contrat n'y entrait pas. Résultat :
  177,67 % en 2024, 152,96 % en 2025. Un second défaut s'y ajoutait, trouvé en mesurant la répartition par contrat : les
  soins d'un contrat n'étaient tirés que sur ses quatre premières années, si bien que 47 % des contrats de santé
  individuelle n'avaient aucune prestation en 2025.
- **Ce qui n'a pas été fait.** Appliquer un facteur global aux montants. Il aurait pu ramener le ratio d'ensemble
  dans la fourchette en laissant des écarts entre branches, parce que les formules n'ont ni les mêmes taux de
  remboursement ni les mêmes plafonds : à échelle égale, les deux branches mesurées donnaient déjà 48,7 % et 55,1 %
  en 2024.
- **Ce qui a été fait.** Les demandes de chaque contrat sont mises à l'échelle pour que leur remboursement théorique égale une
  échelle de sinistralité (par branche) multipliée par la cotisation que le contrat a courue, hors suspension. Chaque
  contrat tire en plus un multiplicateur de consommation à queue lourde : beaucoup de petits consommateurs, une minorité
  de gros. Mesuré : 8,9 % de contrats sans prestation, médiane à 45 % de la cotisation, 10 % des contrats portant 39,9 %
  des remboursements.
- **L'échelle est mesurée, pas déduite.** Plafonds, rejets, contrats sans soin et prestations en cours retranchent une part
  que seule une génération réelle permet de chiffrer. Première échelle à 0,95 : ratio de 49 à 58 %. Échelles retenues
  1,42 et 1,62 : 75,55 à 80,64 % par branche et par exercice complet. Le calibrage a été fait sur une approximation
  rapide (cotisations émises, SQLite), puis le ratio publié a été mesuré sur les cotisations acquises, par dbt.
- **Ce qu'il faut vérifier après coup.** Les corrections antérieures ne doivent pas bouger : plafond cumulé dans l'ordre
  des dates, aucune prestation pendant une suspension, aucun rejet prématuré. Les 18 contrôles de cohérence métier
  les portent déjà ; ils passent sur les deux moteurs. Et le périmètre : la prévoyance reste sans prestation, le ratio
  publié porte sur les produits à prestations déléguées.
- **À retenir.** Quand un indicateur sort de la plausibilité, chercher le lien manquant entre deux flux avant de toucher
  à l'indicateur. Garder un test qui borne le ratio par branche et par exercice (`tests/test_generation.py`), pour qu'un
  futur réglage du générateur ne le fasse pas dériver sans que rien ne le dise.
- **Piège d'environnement rencontré en route.** Après un redémarrage de Docker, `localhost` s'est résolu en IPv6 et chaque
  connexion à PostgreSQL attendait dix secondes avant de retomber en IPv4 : une preuve semblait figée pendant vingt
  minutes. Utiliser `127.0.0.1` dans `COURTAGE_BASE_URL` et `COURTAGE_PG_HOTE`.
