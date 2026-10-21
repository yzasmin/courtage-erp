Une seule ligne dépendant de `date.today()` rendait fausse la reproductibilité annoncée, et aucune preuve du projet ne pouvait s'en apercevoir.

# Une preuve de reproductibilité qui ne pouvait pas échouer

## Ce qui était affirmé

« Génération reproductible : même graine, mêmes données. » L'affirmation était appuyée par une empreinte
SHA-256 publiée, recalculée sur deux exécutions successives, sur deux moteurs de base de données, et
vérifiée par quatre tests.

## Ce qui était vrai

Le générateur calculait l'année de naissance des adhérents ainsi :

```python
naissance = date(date.today().year - age, ...)
```

À graine égale, les âges auraient donc changé au 1er janvier suivant. Et comme l'âge détermine la
cotisation, puis la probabilité de résiliation, l'empreinte entière aurait changé. L'empreinte publiée
aurait cessé de se reproduire le 1er janvier 2027, avec la même graine et la même date de référence.

## Pourquoi aucune preuve ne le voyait

C'est le point qui mérite d'être retenu. Les quatre tests et le script de preuve comparaient deux
exécutions lancées **le même jour, dans le même processus**. Ils ne pouvaient structurellement pas
détecter une dépendance à l'année. Une preuve qui ne peut pas échouer ne prouve rien, même répétée sur
deux moteurs.

Le défaut a été trouvé par une relecture, pas par la suite de tests.

## Le correctif

L'âge se compte depuis la **date de référence** de la simulation, jamais depuis l'horloge :

```python
naissance = date(date_reference.year - age, ...)
```

Et surtout, un test qui peut réellement échouer : deux générations dans deux **sous-processus**, avec
une horloge figée sur deux années différentes et deux `PYTHONHASHSEED` différents, qui exige la même
empreinte.

Le sous-processus n'est pas du luxe. Deux exécutions dans le même processus partagent le grain de
hachage des chaînes, donc l'ordre d'itération des ensembles : une dépendance à cet ordre resterait
invisible. Le test couvre les deux sources de non-déterminisme d'un coup.

Vérification faite avant de conclure : le défaut a été réintroduit volontairement, le test a échoué en
affichant deux empreintes différentes, puis le correctif a été remis et le test est repassé. Un test
qui passe du premier coup ne prouve pas qu'il teste quelque chose.

## Ce qu'il faut en retenir

Pour toute affirmation de reproductibilité, se demander : **qu'est-ce que ma preuve ne peut pas
détecter ?** Ici, deux exécutions simultanées ne pouvaient rien dire du temps. La règle générale :
une preuve de déterminisme doit faire varier tout ce dont le résultat ne doit pas dépendre, c'est-à-dire
au minimum l'horloge, le grain de hachage, le processus et le moteur de base.
