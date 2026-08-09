SELECT
    customer_id,
    customer_name,
    gender,
    age,
    city,
    create_date
FROM {{ ref('stg_customer') }}