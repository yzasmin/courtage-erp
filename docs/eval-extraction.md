Évaluation de l'agent de pré-remplissage (module 4a), écrite par `courtage ia evaluer` le 2026-10-27 à partir de `results/ia_evaluation.json`. Ne pas modifier à la main.

# Évaluation de l'extraction

Modèle `claude-haiku-5-5`, mode `enregistre`. Les 30 documents sont fictifs ; leur vérité terrain est dans
`data/ia/documents/verite_terrain.json`. En mode `enregistre`, les réponses rejouées sont celles d'un
appel réel au modèle, enregistrées avec leur nombre de jetons et leur latence.

## Résultat

| Mesure | Valeur |
| --- | --- |
| Documents lus | 30 sur 30 |
| Précision globale, champ par champ | 96,7 % |
| Documents entièrement exacts | 20 sur 30 |
| Anomalies volontaires relevées par les contrôles | 8 sur 8 |
| Documents sains bloqués à tort | 0 |
| Coût moyen par document | 0,000272 $ |
| Latence moyenne par document | 1807 ms (maximum 3177 ms) |
| Jetons moyens par document | 1778 en entrée, 188 en sortie |

## Précision par champ

| Champ | Précision |
| --- | --- |
| type de document | 100,0 % |
| numéro d'adhérent | 100,0 % |
| nom | 100,0 % |
| prénom | 100,0 % |
| numéro de contrat | 100,0 % |
| date des soins ou de l'attestation | 100,0 % |
| émetteur | 66,7 % |
| garantie invoquée | 100,0 % |
| total écrit | 100,0 % |
| somme des lignes lues | 100,0 % |

## Anomalies volontaires

| Document | Anomalie | Relevée | Message affiché au gestionnaire |
| --- | --- | --- | --- |
| doc-03-demande_remboursement.pdf | nom altere | oui | nom approchant : lu « Julie LAMMBERT », enregistré « Julie Lambert » (similarité 0,96) |
| doc-05-demande_remboursement.pdf | soins avant effet | oui | contrat sans garantie en cours le 28/11/2023 (suspendu ou pas encore en vigueur) |
| doc-07-demande_remboursement.pdf | adherent inexistant | oui | aucun adhérent ne porte le numéro A945230 |
| doc-12-facture_optique.pdf | nom altere | oui | nom approchant : lu « Sylvie LUUCAS », enregistré « Sylvie Lucas » (similarité 0,96) |
| doc-15-facture_optique.pdf | total faux | oui | le total écrit (441,00 €) ne fait pas la somme des lignes (431,00 €) |
| doc-20-facture_dentaire.pdf | nom altere | oui | nom approchant : lu « Celine DUFOOUR », enregistré « Celine Dufour » (similarité 0,96) |
| doc-23-facture_dentaire.pdf | adherent inexistant | oui | aucun adhérent ne porte le numéro A976729 |
| doc-24-facture_dentaire.pdf | total faux | oui | le total écrit (247,92 €) ne fait pas la somme des lignes (237,92 €) |

## Documents sains bloqués à tort

Aucun.

## Erreurs d'extraction

| Document | Champ | Attendu | Lu |
| --- | --- | --- | --- |
| doc-01-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-02-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-03-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-04-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-05-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-06-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-07-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-08-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-09-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |
| doc-10-demande_remboursement.pdf | émetteur | Cabinet Grossiste Delegataire | Cabinet Grossiste Delegataire - Service prestations |

## Rejouer

```bash
python -m uv run --extra ia courtage ia evaluer                 # rejoue les réponses enregistrées
python -m uv run --extra ia courtage ia evaluer --mode api      # appelle le modèle (clé d'API requise)
```
