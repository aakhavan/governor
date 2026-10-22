-- Singular on purpose. dbt_utils is not installed, and this project has no
-- packages.yml, so there is nothing to install with dbt deps. A returned row
-- is a negative MRR amount. Zero (the free plan) is allowed.
select
    mrr_id,
    month_start,
    account_id,
    mrr
from {{ ref('mrr_monthly') }}
where mrr < 0
