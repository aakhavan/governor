-- Singular on purpose. dbt_utils is not installed. A returned row is a plan
-- price outside 0 to 1000 euros. Green prices sit inside that range (the
-- free plan is 0, Enterprise is 799). Error severity, so a source that
-- arrives in cents fails on this model, two hops below the plans source.
{{ config(severity='error') }}

select
    period_id,
    plan_id,
    monthly_price_eur
from {{ ref('int_subscription_periods') }}
where monthly_price_eur < 0
   or monthly_price_eur > 1000
