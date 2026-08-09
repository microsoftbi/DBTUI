SELECT
    product_id,
    product_name,
    category,
    price,
    create_date
FROM {{ ref('stg_product') }}