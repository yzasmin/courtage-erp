Un rappel et une précision globaux ne veulent rien dire quand les contrôles n'ont pas la même nature : les lire contrôle par contrôle a révélé un contrôle inutilisable que la moyenne cachait.

# Une mesure de détection se lit contrôle par contrôle, jamais en moyenne

## Le constat

Le module 2 injecte des anomalies dans les fichiers reçus et compare, à l'arrivée, ce que les contrôles
ont trouvé au manifeste de vérité terrain. La première mesure a donné un rappel d'environ 92 pour cent
et une précision d'environ 35 pour cent, toutes anomalies confondues.

Ce couple de chiffres ne dit rien d'exploitable. Le détail par contrôle, lui, disait tout :

- les contrôles **bloquants** avaient un rappel et une précision de 1,0 : huit anomalies injectées,
  huit trouvées, aucun faux positif ;
- le contrôle du **montant atypique** tournait autour de 0,90 de rappel et 0,91 de précision, ce qui est
  le comportement normal d'un seuil statistique ;
- le contrôle de la **prestation proche du plafond** avait un rappel de 1,0 et une précision de 0,10 :
  sept cent quarante-cinq signalements pour soixante-et-onze anomalies injectées.

La moyenne des trois noyait le seul chiffre qui comptait, et laissait croire à un problème général de
précision alors qu'un seul contrôle était en cause.

## Pourquoi ce contrôle-là dérapait

Deux causes, de nature différente, et il a fallu les séparer.

**Une erreur de conception.** Le contrôle signalait toute prestation d'un adhérent dont la consommation
annuelle dépassait le seuil d'alerte. Un adhérent qui franchit le seuil en mars déclenchait donc une
alerte sur chacune de ses prestations jusqu'en décembre. Un gestionnaire qui reçoit dix alertes pour un
même adhérent n'en lit aucune. Le contrôle ne se déclenche plus que sur la prestation qui **fait
franchir** le seuil : une alerte par adhérent, par garantie et par année, au moment où il reste encore
du plafond à consommer, donc au moment où elle est actionnable.

**Une mesure non comparable.** Même corrigé, ce contrôle garde une précision basse, et c'est normal :
dans ce portefeuille, la consommation de nombreux adhérents atteint réellement le seuil sans qu'aucune
anomalie n'ait été injectée sur eux. Ces signalements sont **justes** ; ils sont seulement absents du
manifeste, qui ne décrit que l'injecté. La précision mesurée contre un manifeste d'injection n'est donc
interprétable que pour les contrôles déterministes, où un faux positif serait un vrai défaut puisqu'il
rejetterait un lot sain.

## Ce qu'il faut en retenir

1. **Publier le détail par contrôle, pas seulement l'ensemble.** La mesure agrégée d'un dispositif
   hétérogène est une moyenne de choses qui ne s'additionnent pas.
2. **Dire pour quels contrôles la précision est interprétable.** Un manifeste d'injection donne un
   rappel exact pour tous les contrôles, et une précision exacte seulement pour ceux dont la condition
   n'est pas satisfaite spontanément par les données.
3. **Ne pas corriger la mesure, corriger le contrôle.** La tentation était de faire décrire par le
   générateur toutes les lignes satisfaisant la condition, ce qui aurait porté la précision à 1,0. Cela
   aurait rendu la mesure circulaire : la vérité terrain aurait été produite par la règle même qu'elle
   évalue. Le chiffre bas a été publié et expliqué.
4. **Une précision basse sur un avertissement est un signal de conception, pas un signal de mesure.**
   C'est ce chiffre qui a fait découvrir que l'alerte se répétait, ce qu'aucune relecture de code
   n'avait relevé.

## Deux défauts trouvés par la même voie

La mesure a aussi révélé deux défauts qui faussaient les chiffres, et qu'aucune relecture n'avait vus.

Le contrôle du total comparait la ligne de total à une somme **incomplète** quand une ligne du fichier
était illisible : la ligne écartée manquait à la somme, et le contrôle fabriquait ainsi une seconde
anomalie à partir de la première. Un lot portant une seule anomalie injectée en signalait deux, et le
rapport renvoyé à l'émetteur l'aurait envoyé sur une fausse piste.

Le contrôle du plafond cumulait la consommation de **l'année entière**, prestations postérieures
comprises. Il regardait donc l'avenir, et signalait en juillet un dépassement qui n'arriverait qu'en
décembre. C'est exactement l'absence de fuite temporelle qu'on exige d'un modèle d'apprentissage, et
elle vaut aussi pour un contrôle de qualité.

## Où regarder dans le dépôt

- `src/courtage/flux/rapport.py`, qui calcule le rappel et la précision par code et par sévérité.
- `src/courtage/flux/controles.py`, fonction `_controle_proche_plafond`, pour la règle de franchissement.
- `results/flux_rapport_detection.json`, pour les valeurs mesurées.
