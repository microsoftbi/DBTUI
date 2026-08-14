{% snapshot snap_customer %}

{{
      config(
        target_schema='snapshots',
        unique_key='customer_id',
        strategy='check',
        check_cols=['customer_level', 'phone'],
      )
  }}

  select
      customer_id,
      customer_name,
      customer_level,
      phone,
      region
  from {{ ref('stg_customer') }}

  {% endsnapshot %}
  
      )
}}