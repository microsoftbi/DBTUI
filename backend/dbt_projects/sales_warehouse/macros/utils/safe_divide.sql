{% macro safe_divide(numerator, denominator, default_value=0) %}
  {#- 安全除法：分母为零或为空时返回默认值，避免 SQL 报错 -#}
  CASE
    WHEN {{ denominator }} = 0 OR {{ denominator }} IS NULL
    THEN {{ default_value }}
    ELSE {{ numerator }} / {{ denominator }}
  END
{% endmacro %}
