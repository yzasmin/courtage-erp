Un projet Power BI en PBIP peut être actualisé, évalué et photographié depuis un script : une commande TMSL envoyée au moteur local remplace le clic sur Actualiser, et les mesures se comparent au SQL sans interface.

# Actualiser et évaluer un PBIP depuis un script

- **Actualisation sans clic.** Le client ADOMD livré avec Power BI exécute du TMSL : `AdomdCommand.ExecuteNonQuery()` avec
  `{"refresh":{"type":"full","objects":[{"database":"<nom>"}]}}` charge toutes les tables depuis leurs sources (ici des
  CSV). Le nom de la base est `$connexion.Database`, un identifiant différent à chaque ouverture. Prolonge la leçon
  `p3-powerbi-verifier-les-mesures.md`, qui ne couvrait que l'évaluation.
- **Chemin de données.** Power BI n'accepte pas de chemin relatif : le projet versionné porte un chemin d'exemple dans le
  paramètre `DossierDonnees`, et le script de construction prend `--dossier-donnees` pour l'adapter. Ne jamais valider
  le chemin réel d'un poste. Les identifiants de lignage sont dérivés d'un compteur (uuid5), pas tirés au hasard, pour
  que deux générations donnent les mêmes fichiers et un diff git lisible.
- **Mesure et format.** Un format `#,0 \€` écrit dans le DAX passe tel quel au TMDL et s'affiche mal : écrire `#,0 €`.
  Les commentaires placés avant une mesure deviennent, en `///`, la description visible dans Power BI : la
  documentation de la mesure et sa définition restent dans un seul fichier.
- **Rapport en JSON classique.** Un segment peut être pré-coché en ajoutant `objects.general[0].properties.filter` à sa
  configuration (clause `In` sur la colonne), et un filtre de rapport se place dans la clé `filters` de `report.json`
  avec `ComparisonKind: 2` pour « supérieur ou égal ». Les deux se sont chargés sans message d'erreur.
- **Capture de la fenêtre.** `SendKeys` avec Ctrl+PageSuivante ne change pas de page dans Power BI. Un clic réel
  (`SetCursorPos` puis `mouse_event`) sur l'onglet de la page le fait. Rendre le processus sensible au DPI avant de
  mesurer le rectangle de la fenêtre, sinon la capture est décalée.
- **Version.** La version réellement installée (2.159.883.0) n'était pas celle annoncée (2.157.1354.0) : relever la
  version par `Get-AppxPackage` et la consigner, plutôt que de recopier celle de la consigne.
