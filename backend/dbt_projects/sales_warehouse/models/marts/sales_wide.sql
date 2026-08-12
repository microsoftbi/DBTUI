SELECT
    f.order_id,
    f.order_date,
    f.customer_id,
    c.customer_name,
    c.gender,
    c.age,
    c.city,
    f.product_id,
    p.product_name,
    p.category,
    p.price,
    f.quantity,
    f.unit_price,
    f.amount,
    f.status,
    -- 使用 safe_divide 宏计算实际单价，避免数量为 0 时报错
    {{ safe_divide('f.amount', 'f.quantity') }} AS actual_unit_price
FROM {{ ref('fact_sales') }} f
LEFT JOIN {{ ref('dim_customer') }} c ON f.customer_id = c.customer_id
LEFT JOIN {{ ref('dim_product') }} p ON f.product_id = p.product_id
