-- Cree la base des metadonnees d'Airflow, utilisee par le module 2.
-- Un seul moteur PostgreSQL pour deux bases : un seul cout memoire fixe sur un poste de 8 Go, et les
-- metadonnees de l'orchestrateur restent separees des donnees metier.
SELECT 'CREATE DATABASE airflow' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
