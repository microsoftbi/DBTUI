SELECT
    order_id,
    order_date,
    customer_id,
    product_id,
    quantity,
    unit_price,
    amount,
    status
FROM {{ source('sales_db', 'salesorder') }}