-- Totals are summed before the join. Joining invoice rows onto accounts
-- would repeat each account and inflate lifetime_billed_eur.
with billed as (
    select
        account_id,
        sum(amount_eur) as lifetime_billed_eur,
        sum(paid_amount_eur) as lifetime_paid_eur
    from {{ ref('int_invoices_with_payments') }}
    group by account_id
)

select
    accounts.account_id,
    accounts.company_name,
    accounts.contact_name,
    accounts.contact_email,
    accounts.country,
    accounts.created_at,
    coalesce(billed.lifetime_billed_eur, 0) as lifetime_billed_eur,
    coalesce(billed.lifetime_paid_eur, 0) as lifetime_paid_eur,
    coalesce(billed.lifetime_billed_eur, 0)
        - coalesce(billed.lifetime_paid_eur, 0) as open_balance_eur
from {{ ref('stg_crm__accounts') }} as accounts
left join billed
    on accounts.account_id = billed.account_id
