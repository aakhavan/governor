select
    payment_id,
    invoice_id,
    cast(paid_at as timestamp) as paid_at,
    cast(amount_eur as decimal(18, 2)) as amount_eur,
    method,
    card_last4,
    cast(_loaded_at as timestamp) as _loaded_at
from {{ source('payments', 'payments') }}
