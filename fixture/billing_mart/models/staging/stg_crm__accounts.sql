select
    account_id,
    company_name,
    contact_name,
    contact_email,
    country,
    cast(created_at as timestamp) as created_at,
    cast(_loaded_at as timestamp) as _loaded_at
from {{ source('crm', 'accounts') }}
