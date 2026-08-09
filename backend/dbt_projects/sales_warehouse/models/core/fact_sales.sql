SELECT
    s.order_id,
    s.order_date,
    s.customer_id,
    s.product_id,
    s.quantity,
    s.unit_price,
    s.amount,
    s.status
FROM {{ ref('stg_salesorder') }} s
WHERE s.status = 'completed'