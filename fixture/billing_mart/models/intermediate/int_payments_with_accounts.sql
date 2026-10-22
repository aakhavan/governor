-- One row per payment, with the account on its invoice. The revenue fact
-- used to join the two staging models itself. An inner join drops a payment
-- whose invoice is missing, and the mart reconciliation test then fails.
select
    payments.payment_id,
    payments.invoice_id,
    invoices.account_id,
    payments.paid_at,
    payments.amount_eur,
    payments.method
from {{ ref('stg_payments__payments') }} as payments
inner join {{ ref('stg_billing__invoices') }} as invoices
    on payments.invoice_id = invoices.invoice_id
