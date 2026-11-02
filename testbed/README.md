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

## Real Olist dataset

Download "Brazilian E-Commerce Public Dataset by Olist" manually from its Kaggle page and unzip the 9 CSVs into `testbed/data/` (git-ignored, never committed).

**TODO (licence): fill in the dataset's licence and attribution here after the licence check.**

## Load

```
python testbed/load_olist.py --source testbed/sample     # synthetic sample, 5 orders
python testbed/load_olist.py --source testbed/data       # real dataset
```

`--dsn` defaults to `GOVERNOR_PG_DSN`. The loader checks that all 9 files exist with the exact Olist headers (including the original spelling `product_name_lenght`), then truncates and loads each `raw.<file stem>` in one transaction, so reruns are idempotent. Columns are text plus `_loaded_at`; typing happens later in silver. It prints one JSON line of row counts.

`testbed/sample/` holds synthetic CSVs (at most 30 rows each) with the edge cases tests rely on: a customer with two `customer_id`s, a canceled order, a late delivery, an order with two reviews, an order with two payments.
