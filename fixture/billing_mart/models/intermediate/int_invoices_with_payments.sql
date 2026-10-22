with payments as (
    select
        invoice_id,
        count(*) as payment_count,
        sum(amount_eur) as paid_amount_eur,
        max(paid_at) as last_paid_at
    from {{ ref('stg_payments__payments') }}
    group by invoice_id
)

select
    invoices.invoice_id,
    invoices.subscription_id,
    invoices.account_id,
    invoices.issued_at,
    invoices.amount_eur,
    invoices.status,
    coalesce(payments.payment_count, 0) as payment_count,
    coalesce(payments.paid_amount_eur, 0) as paid_amount_eur,
    payments.last_paid_at
from {{ ref('stg_billing__invoices') }} as invoices
left join payments
    on invoices.invoice_id = payments.invoice_id
