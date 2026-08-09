SELECT *
FROM {{ ref('sales_wide') }}
WHERE amount <= 0