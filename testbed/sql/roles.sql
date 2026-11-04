-- Database roles for the shop test bed (docs/capstone/design.md section 4).
-- Applied by the admin; idempotent, so it can run any number of times.
--
-- Login passwords come from psql variables:
--   psql "$ADMIN_DSN" -v ask_password="$GOVERNOR_ASK_PASSWORD" \
--        -v build_password="$GOVERNOR_BUILD_PASSWORD" -f testbed/sql/roles.sql
-- or `python testbed/apply_roles.py --dsn <admin dsn>`, which reads the same env
-- variables with the test-bed defaults governor_ask_local / governor_build_local
-- (laptop only, never used in deployment).

-- Roles: create when missing, then set attributes every time.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'governor_analyst') THEN
        CREATE ROLE governor_analyst NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'governor_finance_admin') THEN
        CREATE ROLE governor_finance_admin NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'governor_ask') THEN
        CREATE ROLE governor_ask LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'governor_build') THEN
        CREATE ROLE governor_build LOGIN;
    END IF;
END
$$;

-- Reader roles: no login; their only grants (USAGE and SELECT on serve_<role>) come in C5.
ALTER ROLE governor_analyst NOLOGIN;
ALTER ROLE governor_finance_admin NOLOGIN;

-- ask login: read-only by default, 10 s statement timeout, no direct grants.
-- It is a member of the reader roles without inheriting their rights, so it
-- reads serving views only after the app runs SET ROLE governor_<role>.
ALTER ROLE governor_ask WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'ask_password';
ALTER ROLE governor_ask SET default_transaction_read_only = on;
ALTER ROLE governor_ask SET statement_timeout = '10s';
GRANT governor_analyst TO governor_ask WITH INHERIT FALSE, SET TRUE;
GRANT governor_finance_admin TO governor_ask WITH INHERIT FALSE, SET TRUE;

-- build login (batch 2): CREATE only on dev_governor.
ALTER ROLE governor_build WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'build_password';

-- Schemas.
CREATE SCHEMA IF NOT EXISTS dev_governor;
REVOKE ALL ON SCHEMA dev_governor FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA dev_governor TO governor_build;

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;
REVOKE ALL ON SCHEMA private FROM governor_ask, governor_build, governor_analyst, governor_finance_admin;

-- Nobody but the admin creates objects in public or raw.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_namespace WHERE nspname = 'raw') THEN
        REVOKE ALL ON SCHEMA raw FROM PUBLIC;
    END IF;
END
$$;
