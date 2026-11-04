"""Docker Compose helpers for the capstone test-bed acceptance scripts (C3-C5). Stdlib only."""
from __future__ import annotations

import csv
import os
import sys

from _common import ROOT, check, last_json, run, tail

PROJECT = "governor_accept"
COMPOSE = ["docker", "compose", "-f", "testbed/docker-compose.yml", "-p", PROJECT]
PG = os.environ.get("GOVERNOR_PG_PASSWORD", "governor_local")
ASK_PW = os.environ.get("GOVERNOR_ASK_PASSWORD", "governor_ask_local")
BUILD_PW = os.environ.get("GOVERNOR_BUILD_PASSWORD", "governor_build_local")
# Acceptance runs its own stack on its own port (batch2.md section 3), so a dev test bed on 55432 never collides.
PORT = os.environ.get("GOVERNOR_ACCEPT_PG_PORT", "55433")
ADMIN_DSN = f"postgresql://governor_admin:{PG}@localhost:{PORT}/shop"
ASK_DSN = f"postgresql://governor_ask:{ASK_PW}@localhost:{PORT}/shop"
BUILD_DSN = f"postgresql://governor_build:{BUILD_PW}@localhost:{PORT}/shop"

EXPECTED = {
    "olist_customers_dataset.csv": ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
    "olist_geolocation_dataset.csv": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
    "olist_order_reviews_dataset.csv": ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message", "review_creation_date", "review_answer_timestamp"],
    "olist_orders_dataset.csv": ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
    "olist_products_dataset.csv": ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght", "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"],
    "olist_sellers_dataset.csv": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    "product_category_name_translation.csv": ["product_category_name", "product_category_name_english"],
}


def env(**extra: str) -> dict:
    """The caller's environment with every test-bed setting pinned to the acceptance stack (never inherited)."""
    e = dict(os.environ)
    e.update({"GOVERNOR_PG_PORT": PORT, "GOVERNOR_PG_HOST": "localhost", "GOVERNOR_PG_DB": "shop",
              "GOVERNOR_PG_ADMIN_DSN": ADMIN_DSN, "GOVERNOR_PG_DSN": ASK_DSN, "GOVERNOR_BUILD_DSN": BUILD_DSN,
              "GOVERNOR_BUILD_USER": "governor_build", "GOVERNOR_BUILD_PASSWORD": BUILD_PW,
              "GOVERNOR_ASK_PASSWORD": ASK_PW, "GOVERNOR_PG_PASSWORD": PG})
    e.update(extra)
    return e


def docker_ok() -> bool:
    r = run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=60)
    return check("Docker is running", r.returncode == 0, tail(r) or "docker version failed")


def up() -> bool:
    if not check("testbed/docker-compose.yml exists", (ROOT / "testbed" / "docker-compose.yml").is_file(), "missing"):
        return False
    run(COMPOSE + ["down", "-v"], timeout=300, env=env())
    r = run(COMPOSE + ["up", "-d", "--wait"], timeout=600, env=env())
    return check("compose stack up and healthy", r.returncode == 0, tail(r))


def down() -> None:
    run(COMPOSE + ["down", "-v"], timeout=300, env=env())


def sample_counts() -> dict:
    out = {}
    for name in EXPECTED:
        p = ROOT / "testbed" / "sample" / name
        if p.is_file():
            with p.open(newline="", encoding="utf-8") as f:
                out[name.removesuffix(".csv")] = max(0, sum(1 for _ in csv.reader(f)) - 1)
    return out


def load_sample(label: str = "sample loads into raw") -> dict | None:
    r = run([sys.executable, "testbed/load_olist.py", "--source", "testbed/sample", "--dsn", ADMIN_DSN], timeout=300, env=env())
    d = last_json(r.stdout)
    want = sample_counts()
    ok = isinstance(d, dict) and {k: int(v) for k, v in d.items()} == want
    check(label, ok, f"got {d} want {want}" if not ok else f"{len(want)} tables")
    return d if ok else None


def apply_roles(label: str = "roles applied") -> bool:
    r = run([sys.executable, "testbed/apply_roles.py", "--dsn", ADMIN_DSN], timeout=300, env=env())
    return check(label, r.returncode == 0, tail(r))
