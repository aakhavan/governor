-- A row here means lifetime billed on the account mart does not add up
-- to the invoice staging table (tolerance 0.01 euro). Error severity, so
-- a fan-out join fails in the mart.
{{ config(severity='error') }}

with accounts as (
    select coalesce(sum(lifetime_billed_eur), 0) as total_eur
    from {{ ref('dim_accounts') }}
),

invoices as (
    select coalesce(sum(amount_eur), 0) as total_eur
    from {{ ref('stg_billing__invoices') }}
)

select
    accounts.total_eur as billed_eur,
    invoices.total_eur as invoices_eur
from accounts
cross join invoices
where abs(accounts.total_eur - invoices.total_eur) > 0.01
