-- Cash revenue: payments summed to the account and the day they were paid.
select
    account_id || '|' || strftime(cast(paid_at as date), '%Y-%m-%d') as revenue_id,
    cast(paid_at as date) as revenue_date,
    account_id,
    count(*) as payment_count,
    sum(amount_eur) as amount_eur
from {{ ref('int_payments_with_accounts') }}
group by 1, 2, 3
