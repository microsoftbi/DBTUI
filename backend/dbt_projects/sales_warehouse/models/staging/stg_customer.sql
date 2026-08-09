SELECT
    customer_id,
    customer_name,
    gender,
    age,
    city,
    create_date
FROM {{ source('sales_db', 'customer') }}