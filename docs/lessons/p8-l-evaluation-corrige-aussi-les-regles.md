Une évaluation sur vérité terrain corrige les règles autant que le modèle : elle a trouvé une règle métier trop stricte, et les tests un seuil trop lâche ; la vérité terrain, elle, ne se retouche pas après avoir vu les résultats.

# L'évaluation de l'agent corrige aussi les règles

**Contexte.** Module 4a, 27/10/2026. Trente documents fictifs, une vérité terrain, Claude Haiku 5.5 en
sortie structurée stricte, puis des contrôles métier écrits en Python.

**Ce que les mesures ont trouvé.**

- **Un seuil trop lâche, trouvé par les tests.** La similarité du nom était jugée conforme à partir de 0,97.
  Or une lettre doublée dans « Camille Teissier » donne exactement 0,97 : la faute passait sans signalement.
  La règle est devenue : conforme seulement si le nom est identique après normalisation, alerte au-delà de
  0,80, blocage en dessous (D44).
- **Une règle trop stricte, trouvée par l'évaluation.** Une attestation d'employeur saine était bloquée :
  elle était datée pendant la suspension pour impayé du contrat collectif. Le contrôle disait vrai, mais
  une attestation ne paie rien ; le blocage n'a de sens que pour un remboursement (D45).
- **Un désaccord sur la vérité terrain, laissé tel quel.** Les dix seules erreurs d'extraction portent sur
  l'émetteur des demandes de remboursement : le modèle lit « Cabinet Grossiste Delegataire - Service
  prestations », la vérité terrain attend le nom du cabinet seul. On pourrait défendre les deux. Changer la
  vérité terrain après avoir vu le résultat aurait gonflé la précision de 96,7 % à 100 % : c'est
  précisément ce qu'une évaluation ne doit pas permettre.

**Ce qui a rendu cela possible à faible coût.** Les trente réponses réelles sont enregistrées avec leur
coût, leur latence et l'empreinte de la requête. Une modification des contrôles se remesure hors ligne en
quelques secondes et sans frais ; une modification des instructions invalide l'empreinte et oblige à
réenregistrer, au lieu de mesurer un ancien comportement.

**Un piège d'accès.** Une clé d'API personnelle (préfixe `sk-ant-usr`) n'est rattachée à aucun espace de
travail : l'API refuse l'appel tant que l'en-tête `anthropic-workspace-id` manque. Le code le lit dans
`ANTHROPIC_WORKSPACE_ID` ; une clé d'espace de travail s'en passe.
