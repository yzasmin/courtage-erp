{% macro tranche_age(age) %}
-- Tranche d'age de la restitution. Une seule definition pour la dimension adherent et pour les
-- mouvements de portefeuille : deux CASE recopies finissent toujours par diverger.
case
    when {{ age }} is null then 'inconnu'
    when {{ age }} < 25 then 'moins de 25 ans'
    when {{ age }} < 35 then '25 a 34 ans'
    when {{ age }} < 45 then '35 a 44 ans'
    when {{ age }} < 55 then '45 a 54 ans'
    when {{ age }} < 65 then '55 a 64 ans'
    else '65 ans et plus'
end
{% endmacro %}
