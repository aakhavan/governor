-- One row per subscription per month it was active. There is no plan-change
-- history, so the monthly price is the plan price for every month in the life
-- of the subscription. A subscription counts in a month when it started
-- before the month ended and was not cancelled before the month started.
with months as (
    select cast(generate_series as date) as month_start
    from generate_series(
        timestamp '{{ var("window_start") }}',
        timestamp '{{ var("window_month_end") }}',
        interval 1 month
    )
),

priced as (
    select
        subscriptions.subscription_id,
        subscriptions.account_id,
        subscriptions.plan_id,
        subscriptions.started_at,
        subscriptions.cancelled_at,
        plans.monthly_price_eur
    from {{ ref('stg_billing__subscriptions') }} as subscriptions
    inner join {{ ref('stg_billing__plans') }} as plans
        on subscriptions.plan_id = plans.plan_id
)

select
    priced.subscription_id || '|' || strftime(months.month_start, '%Y-%m-%d') as period_id,
    months.month_start,
    priced.subscription_id,
    priced.account_id,
    priced.plan_id,
    priced.monthly_price_eur
from months
inner join priced
    on priced.started_at < months.month_start + interval 1 month
    and (
        priced.cancelled_at is null
        or priced.cancelled_at >= months.month_start
    )
