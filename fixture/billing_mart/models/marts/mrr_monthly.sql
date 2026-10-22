with by_account as (
    select
        month_start,
        account_id,
        count(*) as active_subscriptions,
        sum(monthly_price_eur) as mrr
    from {{ ref('int_subscription_periods') }}
    group by month_start, account_id
)

select
    account_id || '|' || strftime(month_start, '%Y-%m-%d') as mrr_id,
    month_start,
    account_id,
    active_subscriptions,
    mrr
from by_account
