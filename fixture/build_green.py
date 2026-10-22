"""Build the green billing mart and publish artifacts/green.

Order matters on Windows. DuckDB locks warehouse.duckdb, so this script
closes its connection before dbt starts. dbt itself runs in a subprocess
and that process exits before the warehouse is copied.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

import generate_raw
import load_raw

SPRINT_DIR = Path(__file__).resolve().parents[1]
DBT_DIR = SPRINT_DIR / "fixture" / "billing_mart"
TARGET_DIR = DBT_DIR / "target"
GREEN_DIR = SPRINT_DIR / "artifacts" / "green"
WAREHOUSE = DBT_DIR / "warehouse.duckdb"

RAW_TABLES = ("plans", "accounts", "subscriptions", "invoices", "payments")
MARTS = ("dim_accounts", "fct_revenue_daily", "mrr_monthly")
ARTIFACTS = ("manifest.json", "run_results.json", "sources.json", "catalog.json")

EXPECTED_RAW = {
    "plans": len(generate_raw.PLANS),
    "accounts": generate_raw.N_ACCOUNTS,
    "subscriptions": generate_raw.N_SUBSCRIPTIONS,
    "invoices": generate_raw.N_INVOICES,
    "payments": generate_raw.N_PAYMENTS,
}


def _dbt_executable() -> Path:
    scripts = Path(sys.executable).resolve().parent
    for name in ("dbt.exe", "dbt"):
        candidate = scripts / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"dbt is not installed next to {sys.executable}")


def _run_dbt(args: list[str], warehouse: Path) -> None:
    command = [
        str(_dbt_executable()),
        *args,
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
        "--no-use-colors",
    ]
    print("\n$ dbt " + " ".join(args), flush=True)
    env = os.environ.copy()
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    env["DO_NOT_TRACK"] = "1"
    # Absolute path so the file load_raw just wrote is the one dbt opens,
    # whatever the process current directory is.
    env["BILLING_MART_DUCKDB"] = str(warehouse.resolve())
    completed = subprocess.run(command, cwd=DBT_DIR, env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _require_statuses(path: Path, allowed: set[str], expected_count: int | None = None) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload["results"]
    if expected_count is not None and len(results) != expected_count:
        raise SystemExit(f"{path.name}: expected {expected_count} results, got {len(results)}")
    bad = []
    for result in results:
        status = result["status"]
        if status not in allowed:
            bad.append(f"{result.get('unique_id', '?')} {status}")
    if bad:
        raise SystemExit(f"{path.name} is not green:\n" + "\n".join(bad))


def _checkpoint(warehouse: Path) -> None:
    connection = duckdb.connect(str(warehouse))
    try:
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    wal = Path(str(warehouse) + ".wal")
    if wal.exists():
        wal.unlink()


def _publish(warehouse: Path, as_of_text: str) -> None:
    GREEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACTS:
        shutil.copy2(TARGET_DIR / name, GREEN_DIR / name)
    destination = GREEN_DIR / "warehouse.duckdb"
    stale_wal = Path(str(destination) + ".wal")
    if stale_wal.exists():
        stale_wal.unlink()
    shutil.copy2(warehouse, destination)
    (GREEN_DIR / "as_of.txt").write_text(as_of_text + "\n", encoding="utf-8", newline="\n")


def _print_csv_hashes(raw_dir: Path) -> None:
    for name in generate_raw.FILES:
        path = raw_dir / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"sha256 {name} {digest}")


def _print_summary(warehouse: Path) -> None:
    # Read-only, and closed before the function returns. Nothing dbt-related
    # runs after this.
    connection = duckdb.connect(str(warehouse), read_only=True)
    try:
        for name in RAW_TABLES:
            count = connection.execute(f"select count(*) from raw.{name}").fetchone()[0]
            print(f"raw.{name} {count}")
        for name in MARTS:
            count = connection.execute(f"select count(*) from marts.{name}").fetchone()[0]
            print(f"marts.{name} {count}")
        invoice_sum = connection.execute("select sum(amount_eur) from raw.invoices").fetchone()[0]
        payment_sum = connection.execute("select sum(amount_eur) from raw.payments").fetchone()[0]
        mrr_sum = connection.execute("select sum(mrr) from marts.mrr_monthly").fetchone()[0]
        print(f"sum raw.invoices.amount_eur {invoice_sum}")
        print(f"sum raw.payments.amount_eur {payment_sum}")
        print(f"sum marts.mrr_monthly.mrr {mrr_sum}")
    finally:
        connection.close()


def _print_named_result(path: Path, name: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        result
        for result in payload["results"]
        if name in str(result.get("unique_id", ""))
    ]
    if len(matches) != 1:
        raise SystemExit(f"{path.name} has {len(matches)} results for {name}")
    status = matches[0]["status"]
    print(f"test {name} {status}")
    if status != "pass":
        raise SystemExit(f"{name} is {status}")


def _print_freshness(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for result in payload["results"]:
        print(f"freshness {result['unique_id']} {result['status']}")


def main() -> None:
    started = time.perf_counter()
    # Same instant is written into _loaded_at (UTC, no offset) and as_of.txt.
    loaded_at = datetime.now(timezone.utc).replace(microsecond=0)
    as_of_text = loaded_at.isoformat(timespec="seconds")
    print(f"as_of {as_of_text}")

    raw_dir = generate_raw.write_csvs()
    _print_csv_hashes(raw_dir)

    counts = load_raw.load(WAREHOUSE, raw_dir, loaded_at)
    for name, count in counts.items():
        expected = EXPECTED_RAW[name]
        if count != expected:
            raise SystemExit(f"raw.{name} has {count} rows, expected {expected}")
        print(f"loaded raw.{name} {count}")

    _run_dbt(["build"], WAREHOUSE)
    build_results = TARGET_DIR / "run_results.json"
    held_results = TARGET_DIR / "run_results_build.json"
    shutil.copy2(build_results, held_results)
    _run_dbt(["source", "freshness"], WAREHOUSE)
    _run_dbt(["docs", "generate"], WAREHOUSE)
    # Freshness writes sources.json. Keep the build's run_results, which has
    # the model and test rows, in case a later command replaced that file.
    shutil.copy2(held_results, build_results)
    held_results.unlink()

    # Exposures are part of `dbt build` and finish as no-op. That is success:
    # nothing is executed for them. Tests and models must still pass.
    _require_statuses(build_results, {"success", "pass", "no-op"})
    _print_named_result(build_results, "assert_plan_prices_in_range")
    _require_statuses(TARGET_DIR / "sources.json", {"pass"}, expected_count=2)
    _print_freshness(TARGET_DIR / "sources.json")

    _checkpoint(WAREHOUSE)
    _publish(WAREHOUSE, as_of_text)
    print("published artifacts/green")
    _print_summary(GREEN_DIR / "warehouse.duckdb")
    elapsed = time.perf_counter() - started
    print(f"elapsed_s {elapsed:.1f}")
    if elapsed >= 60:
        raise SystemExit(f"build took {elapsed:.1f}s, the limit is 60s")


if __name__ == "__main__":
    main()
