"""Write a perturbed copy of the Olist CSVs for one holdout run (batch2d section 24). Stdlib only, deterministic.

Usage: python testbed/perturb.py --source <olist dir> --out <dir> --policy knowledge/shop/policy.yaml

Every table and column gets a new, abbreviated name from the fixed mapping below, column order is reversed,
the orders table is split into a header and a delivery table, and a junk table `etl_audit_log` is added.
Values and row order are never touched. Also writes `mapping.json` and `policy.yaml` (PII columns renamed).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_olist import EXPECTED, HeaderError, validate_source  # noqa: E402

TABLES: dict[str, str] = {
    "olist_customers_dataset": "cust",
    "olist_geolocation_dataset": "geo_zip",
    "olist_order_items_dataset": "ord_line",
    "olist_order_payments_dataset": "ord_pay",
    "olist_order_reviews_dataset": "ord_rvw",
    "olist_orders_dataset": "ord_hdr",
    "olist_products_dataset": "prod",
    "olist_sellers_dataset": "slr",
    "product_category_name_translation": "cat_xlat",
}

# The orders table is split: these columns go to the delivery table, the rest (and the order id) stay in the header.
ORDERS = "olist_orders_dataset"
DELIVERY_TABLE = "ord_dlv"
DELIVERY_COLUMNS = ("order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date")
ORDER_KEY = "order_id"

# One new name per original column name, the same in every table, so keys still join and the flat policy maps 1:1.
COLUMNS: dict[str, str] = {
    "customer_id": "cust_ref",
    "customer_unique_id": "cust_uid",
    "customer_zip_code_prefix": "cust_zip5",
    "customer_city": "cust_town",
    "customer_state": "cust_uf",
    "geolocation_zip_code_prefix": "geo_zip5",
    "geolocation_lat": "geo_y",
    "geolocation_lng": "geo_x",
    "geolocation_city": "geo_town",
    "geolocation_state": "geo_uf",
    "order_id": "ord_ref",
    "order_item_id": "line_no",
    "product_id": "prod_ref",
    "seller_id": "slr_ref",
    "shipping_limit_date": "ship_lim_ts",
    "price": "unit_amt",
    "freight_value": "frt_amt",
    "payment_sequential": "pay_seq",
    "payment_type": "pay_kind",
    "payment_installments": "pay_parts",
    "payment_value": "pay_amt",
    "review_id": "rvw_ref",
    "review_score": "rvw_stars",
    "review_comment_title": "rvw_ttl",
    "review_comment_message": "rvw_txt",
    "review_creation_date": "rvw_sent_ts",
    "review_answer_timestamp": "rvw_ans_ts",
    "order_status": "ord_stat",
    "order_purchase_timestamp": "purch_ts",
    "order_approved_at": "appr_ts",
    "order_delivered_carrier_date": "carr_ts",
    "order_delivered_customer_date": "dlv_ts",
    "order_estimated_delivery_date": "est_dlv_ts",
    "product_category_name": "cat_pt",
    "product_name_lenght": "nm_len",
    "product_description_lenght": "desc_len",
    "product_photos_qty": "pics_n",
    "product_weight_g": "wt_g",
    "product_length_cm": "len_cm",
    "product_height_cm": "ht_cm",
    "product_width_cm": "wd_cm",
    "seller_zip_code_prefix": "slr_zip5",
    "seller_city": "slr_town",
    "seller_state": "slr_uf",
    "product_category_name_english": "cat_en",
}

JUNK_TABLE = "etl_audit_log"
JUNK_COLUMNS = ["batch_id", "loaded_at", "row_count", "status"]
JUNK_ROWS = 20


class PerturbError(Exception):
    pass


def check_mapping() -> None:
    """The fixed mapping covers every Olist table and column, is unique, and never reuses an original name."""
    old_tables = {n.removesuffix(".csv") for n in EXPECTED}
    old_cols = {c for cols in EXPECTED.values() for c in cols}
    problems: list[str] = []
    if set(TABLES) != old_tables:
        problems.append(f"table mapping does not match the Olist tables: {sorted(set(TABLES) ^ old_tables)}")
    if set(COLUMNS) != old_cols:
        problems.append(f"column mapping does not match the Olist columns: {sorted(set(COLUMNS) ^ old_cols)}")
    new_tables = [*TABLES.values(), DELIVERY_TABLE, JUNK_TABLE]
    if len(set(new_tables)) != len(new_tables) or len(set(COLUMNS.values())) != len(COLUMNS):
        problems.append("new names are not unique")
    if (set(new_tables) | set(COLUMNS.values()) | set(JUNK_COLUMNS)) & (old_tables | old_cols):
        problems.append("a new name reuses an original table or column name")
    if problems:
        raise PerturbError("; ".join(problems))


def _read(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _project(header: list[str], rows: list[list[str]], keep: list[str], new_table: str,
             mapping: dict[str, str], old_table: str, record: bool = True) -> tuple[str, list[str], list[list[str]]]:
    """Keep ``keep`` columns in reversed order under their new names; record old -> new in ``mapping``."""
    order = list(reversed(keep))
    idx = [header.index(c) for c in order]
    if record:
        for c in order:
            mapping[f"{old_table}.{c}"] = f"{new_table}.{COLUMNS[c]}"
    return new_table, [COLUMNS[c] for c in order], [[r[i] for i in idx] for r in rows]


def junk_rows() -> list[list[str]]:
    """20 synthetic audit rows; fixed values so every run is identical."""
    statuses = ("ok", "ok", "ok", "retry", "ok")
    return [[f"B{n:04d}", f"2017-01-{1 + n // 4:02d} {6 * (n % 4):02d}:00:00", str(1000 + 37 * n), statuses[n % 5]]
            for n in range(JUNK_ROWS)]


def read_policy(path: Path) -> list[tuple[str, str]]:
    """The flat ``column: tag`` policy, in file order (comments and blank lines skipped)."""
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].strip()
        if not s:
            continue
        if ":" not in s:
            raise PerturbError(f"policy line is not 'column: tag': {line!r}")
        key, tag = (p.strip() for p in s.split(":", 1))
        pairs.append((key, tag))
    return pairs


def rename_policy(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    unknown = [k for k, _ in pairs if k not in COLUMNS]
    if unknown:
        raise PerturbError(f"policy names columns that are not Olist columns: {unknown}")
    return [(COLUMNS[k], tag) for k, tag in pairs]


def perturb(source: Path, out: Path, policy: Path) -> dict:
    check_mapping()
    validate_source(source)
    pairs = rename_policy(read_policy(policy))
    out.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    counts: dict[str, int] = {}
    for name in EXPECTED:
        old = name.removesuffix(".csv")
        header, rows = _read(source / name)
        if old == ORDERS:
            head_cols = [c for c in header if c not in DELIVERY_COLUMNS]
            # the delivery table also carries the order id; mapping.json maps it once, to the header table
            parts = [_project(header, rows, head_cols, TABLES[old], mapping, old),
                     _project(header, rows, [ORDER_KEY, *DELIVERY_COLUMNS], DELIVERY_TABLE, mapping, old,
                              record=False)]
            mapping |= {f"{old}.{c}": f"{DELIVERY_TABLE}.{COLUMNS[c]}" for c in DELIVERY_COLUMNS}
        else:
            parts = [_project(header, rows, header, TABLES[old], mapping, old)]
        for table, cols, data in parts:
            _write(out / f"{table}.csv", cols, data)
            counts[table] = len(data)
    _write(out / f"{JUNK_TABLE}.csv", JUNK_COLUMNS, junk_rows())
    counts[JUNK_TABLE] = JUNK_ROWS
    doc = {"tables": dict(TABLES), "columns": mapping}
    (out / "mapping.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    lines = [f"# {policy.name} renamed by testbed/perturb.py: column -> PII tag, same flat format.",
             *(f"{k}: {v}" for k, v in pairs)]
    (out / "policy.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--policy", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        counts = perturb(args.source, args.out, args.policy)
    except (HeaderError, PerturbError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
