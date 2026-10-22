-- One row per invoice with what has been paid against it.
-- days_outstanding counts calendar days from issue to the build's as_of
-- (dbt var as_of, set by build_green.py). It never reads the wall clock,
-- so the same build answers the same way whenever it is queried.
with invoices as (
    select
        invoice_id,
        subscription_id,
        account_id,
        issued_at,
        amount_eur,
        status,
        paid_amount_eur,
        last_paid_at,
        paid_amount_eur >= amount_eur as is_fully_paid
    from {{ ref('int_invoices_with_payments') }}
)

select
    invoices.invoice_id,
    invoices.account_id,
    invoices.subscription_id,
    accounts.country,
    invoices.issued_at,
    invoices.amount_eur,
    invoices.status,
    invoices.paid_amount_eur,
    invoices.last_paid_at,
    invoices.is_fully_paid,
    case
        when invoices.is_fully_paid then 0
        else date_diff('day', invoices.issued_at, cast('{{ var("as_of") }}' as timestamp))
    end as days_outstanding
from invoices
left join {{ ref('stg_crm__accounts') }} as accounts
    on invoices.account_id = accounts.account_id
