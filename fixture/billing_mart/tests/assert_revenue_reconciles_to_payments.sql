-- A row here means daily revenue does not add up to the payment staging
-- table (tolerance 0.01 euro). Error severity, so a fan-out join fails
-- in the mart rather than on the staging model next to the source.
{{ config(severity='error') }}

with revenue as (
    select coalesce(sum(amount_eur), 0) as total_eur
    from {{ ref('fct_revenue_daily') }}
),

payments as (
    select coalesce(sum(amount_eur), 0) as total_eur
    from {{ ref('stg_payments__payments') }}
)

select
    revenue.total_eur as revenue_eur,
    payments.total_eur as payments_eur
from revenue
cross join payments
where abs(revenue.total_eur - payments.total_eur) > 0.01
