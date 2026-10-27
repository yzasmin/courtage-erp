Un modèle simple qui atteint presque le plafond théorique ne se remplace pas par un modèle plus complexe qui ne fait pas mieux ; le plafond n'est calculable qu'avec un générateur connu, et il faut s'en servir.

# Mesurer le modèle contre le plafond du générateur

**Contexte.** Module 5, 27/10/2026. La spécification demandait une référence interprétable, puis un modèle
plus performant. Sur l'année de test, la régression logistique et LightGBM ont la même ROC-AUC (0,645),
et LightGBM est moins bon sur la PR-AUC, le lift du premier décile et la calibration.

**Ce qui aurait été facile et faux.** Déployer LightGBM parce que c'était le plan, ou regarder 0,645 et
conclure que les deux modèles sont médiocres.

**Ce qui a tranché.** Les données sont synthétiques, donc la vraie probabilité de chaque résiliation est
connue : c'est la formule du générateur. Recalculée sur les mêmes contrats, elle ne dépasse pas 0,662.
Chaque résiliation est un tirage au sort, et aucun modèle ne fait mieux que la règle qui a servi à tirer.
La régression logistique est donc à presque tout le signal disponible, et LightGBM n'a rien de plus à
trouver : les causes se combinent par facteurs multiplicatifs, exactement la forme d'un modèle logistique.

**La règle.** Sur des données simulées, calculer le plafond à partir du générateur avant de juger un
score. Déployer le modèle qui gagne à la mesure, pas celui que le plan désignait, et garder l'autre en
comparaison à chaque apprentissage. Sur des données réelles, le plafond est inconnu ; la comparaison des
deux modèles reste la seule protection.

**Deux défauts trouvés en chemin.**

- Le générateur déclarait deux facteurs de sinistralité qu'il n'appliquait pas : les prestations sont
  générées après les contrats. La documentation affirmait l'effet. Elle a été corrigée, sans toucher au
  générateur pour ne pas changer les chiffres des modules précédents.
- Sous Windows, une connexion à `localhost` vers le PostgreSQL du compose attendait environ deux minutes
  avant de réussir, ce qui gonflait chaque commande. `127.0.0.1` répond immédiatement : le scoring est
  passé de plusieurs minutes à 15 secondes, l'apprentissage de 137 à 3 secondes.
