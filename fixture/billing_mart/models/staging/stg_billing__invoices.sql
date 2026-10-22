select
    invoice_id,
    subscription_id,
    account_id,
    cast(issued_at as timestamp) as issued_at,
    cast(amount_eur as decimal(18, 2)) as amount_eur,
    status
from {{ source('billing', 'invoices') }}
