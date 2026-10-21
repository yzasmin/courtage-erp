{% test montant_non_negatif(model, column_name) %}
-- Test generique du projet : une colonne de montant ne porte jamais de valeur negative.
--
-- Ecrit a la main plutot que tire de `dbt_utils` : une dependance externe de plusieurs dizaines de
-- macros pour un test de deux lignes ne se justifie pas, et un paquet de moins est un paquet de moins
-- a maintenir lors d'une montee de version.
select {{ column_name }} as valeur
from {{ model }}
where {{ column_name }} < 0
{% endtest %}
