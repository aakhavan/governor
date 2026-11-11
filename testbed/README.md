# Postgres test bed

A local Postgres 16 (database `shop`, host port 55432) holding the Olist e-commerce tables in schema `raw`, used by the capstone steps. Laptop only: the default password is `governor_local`; set `GOVERNOR_PG_PASSWORD` to change it.

## Start and stop

```
docker compose -f testbed/docker-compose.yml up -d --wait
docker compose -f testbed/docker-compose.yml down        # keep the data volume
docker compose -f testbed/docker-compose.yml down -v     # also delete the data
```

DSN for the admin user: `postgresql://governor_admin:governor_local@localhost:55432/shop`
(export it as `GOVERNOR_PG_DSN`; code reads connection settings from env only).

The host port is `${GOVERNOR_PG_PORT:-55432}`; set `GOVERNOR_PG_PORT` to move the stack. Acceptance runs its own stack (compose project `governor_accept`) on port 55433 with its own DSNs, so it never collides with this dev test bed.

## Real Olist dataset

Download "Brazilian E-Commerce Public Dataset by Olist" manually from its Kaggle page and unzip the 9 CSVs into `testbed/data/` (git-ignored, never committed).

Licence: the Olist data is CC BY-NC-SA 4.0. Credit: Olist ("Brazilian E-Commerce Public Dataset by Olist"). The data is never committed, and derived tables (including the perturbed copy below) stay under the same licence.

## Load

```
python testbed/load_olist.py --source testbed/sample     # synthetic sample, 5 orders
python testbed/load_olist.py --source testbed/data       # real dataset
```

`--dsn` defaults to `GOVERNOR_PG_DSN`. The loader checks that all 9 files exist with the exact Olist headers (including the original spelling `product_name_lenght`), then truncates and loads each `raw.<file stem>` in one transaction, so reruns are idempotent. Columns are text plus `_loaded_at`; typing happens later in silver. It prints one JSON line of row counts.

`testbed/sample/` holds synthetic CSVs (at most 30 rows each) with the edge cases tests rely on: a customer with two `customer_id`s, a canceled order, a late delivery, an order with two reviews, an order with two payments.

## Perturbed holdout

One holdout run on data governor has not seen: the same Olist rows under new, abbreviated table and column names, column order reversed, the orders table split into `ord_hdr` and `ord_dlv`, and a junk table `etl_audit_log` that no KPI needs. Values and row order are untouched, so the frozen gold values in `evaluation/build_gold/olist_gold.yaml` still apply. `perturb.py` is deterministic (fixed mapping in the script, stdlib only) and checks the source headers like `load_olist.py`. Next to the CSVs it writes `mapping.json` (old -> new names) and `policy.yaml` (the shop policy with every PII column renamed).

```
python testbed/perturb.py --source testbed/data --out <perturbed dir> --policy knowledge/shop/policy.yaml
python testbed/load_csv_dir.py --source <perturbed dir> --replace
python -m governor.eval.build_eval --system agent    --gold evaluation/build_gold/olist_gold.yaml --out <agent report>.json    --policy <perturbed dir>/policy.yaml
python -m governor.eval.build_eval --system baseline --gold evaluation/build_gold/olist_gold.yaml --out <baseline report>.json --policy <perturbed dir>/policy.yaml
python testbed/load_csv_dir.py --source testbed/data --replace    # put the original Olist tables back
```

Keep `<perturbed dir>` outside the repo (it holds real data). `load_csv_dir.py` loads every `*.csv` in the folder into `raw.<file stem>` (text columns plus `_loaded_at`, one transaction per table) and prints one JSON line of row counts. It refuses to load while `raw` holds tables unless `--replace` is given, which drops every table in `raw` first, so two datasets never mix. It touches no other schema and never drops with CASCADE: if something outside `raw` depends on a raw table, the drop fails and nothing changes. Restore with `load_csv_dir.py --replace` as above: `load_olist.py` alone would leave the perturbed tables next to the original ones.

**Rule: run it once and report whatever comes out.** No tuning of prompts, code or knowledge between looking at the perturbed results and reporting them; a second run would no longer be a holdout.
