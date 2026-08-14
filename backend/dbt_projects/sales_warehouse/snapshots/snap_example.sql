{% snapshot snap_example %}

{{
    config(
      target_schema='snapshots',
      unique_key='id',
      strategy='check',
      check_cols=['id'],
    )
}}

select id from {{ ref('example') }}

{% endsnapshot %}
