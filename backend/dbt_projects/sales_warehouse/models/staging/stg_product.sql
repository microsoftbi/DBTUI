SELECT
    product_id,
    product_name,
    category,
    price,
    create_date
FROM {{ source('sales_db', 'product') }}