---
title: Courtage ERP
emoji: 📑
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Mini-ERP de courtage santé et prévoyance, données fictives
---

# Courtage ERP, démonstration en ligne

Mini-ERP d'un courtier grossiste délégataire en santé et prévoyance, sur un portefeuille entièrement
fictif : fiche contrat et ses avenants, anomalies de rapprochement des flux financiers, réseau d'apporteurs
et délégations, score de résiliation sur la fiche adhérent, et dossiers pré-remplis par un modèle de
langage en attente de validation.

La démonstration est ouverte à tous et sans authentification. Sa base est remise à zéro à chaque
redémarrage. Elle ne contient que l'interface : la chaîne Airflow, dbt et le tableau de bord Power BI
tournent sur PostgreSQL et sont décrits dans le dépôt.

Code source, mesures et documentation : https://github.com/yzasmin/courtage-erp
