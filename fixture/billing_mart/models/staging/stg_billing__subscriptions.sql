select
    subscription_id,
    account_id,
    plan_id,
    status,
    cast(started_at as timestamp) as started_at,
    cast(cancelled_at as timestamp) as cancelled_at
from {{ source('billing', 'subscriptions') }}
