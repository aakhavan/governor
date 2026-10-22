select
    plan_id,
    plan_name,
    cast(monthly_price_eur as decimal(18, 2)) as monthly_price_eur
from {{ source('billing', 'plans') }}
