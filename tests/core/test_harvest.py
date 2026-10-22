"""Harvest projects dbt artifacts into the seven meta tables."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

import duckdb
import pytest
import yaml

from triage.config import PROJECT_DIR
from triage.harvest import TABLE_NAMES, HarvestError, harvest, load_tables, main

GREEN = PROJECT_DIR / "artifacts" / "green"
ARTIFACTS = ("manifest.json", "catalog.json", "run_results.json", "sources.json")

# 5 sources, 10 model-to-model hops, 3 model-to-exposure hops.
EXPECTED_EDGES = {
    ("source.billing_mart.billing.invoices", "model.billing_mart.stg_billing__invoices"),
    ("source.billing_mart.billing.plans", "model.billing_mart.stg_billing__plans"),
    ("source.billing_mart.billing.subscriptions", "model.billing_mart.stg_billing__subscriptions"),
    ("source.billing_mart.crm.accounts", "model.billing_mart.stg_crm__accounts"),
    ("source.billing_mart.payments.payments", "model.billing_mart.stg_payments__payments"),
    ("model.billing_mart.stg_billing__invoices", "model.billing_mart.int_invoices_with_payments"),
    ("model.billing_mart.stg_billing__invoices", "model.billing_mart.int_payments_with_accounts"),
    ("model.billing_mart.stg_billing__plans", "model.billing_mart.int_subscription_periods"),
    ("model.billing_mart.stg_billing__subscriptions", "model.billing_mart.int_subscription_periods"),
    ("model.billing_mart.stg_crm__accounts", "model.billing_mart.dim_accounts"),
    ("model.billing_mart.stg_payments__payments", "model.billing_mart.int_invoices_with_payments"),
    ("model.billing_mart.stg_payments__payments", "model.billing_mart.int_payments_with_accounts"),
    ("model.billing_mart.int_invoices_with_payments", "model.billing_mart.dim_accounts"),
    ("model.billing_mart.int_payments_with_accounts", "model.billing_mart.fct_revenue_daily"),
    ("model.billing_mart.int_subscription_periods", "model.billing_mart.mrr_monthly"),
    ("model.billing_mart.dim_accounts", "exposure.billing_mart.collections_report"),
    ("model.billing_mart.fct_revenue_daily", "exposure.billing_mart.finance_dashboard"),
    ("model.billing_mart.mrr_monthly", "exposure.billing_mart.finance_dashboard"),
}


def _copy_green(destination: Path) -> None:
    for name in ARTIFACTS:
        shutil.copyfile(GREEN / name, destination / name)


def test_green_graph_is_sources_models_and_exposures():
    tables = load_tables(GREEN)
    nodes = tables["nodes"]
    assert len(nodes) == 18
    assert Counter(row["resource_type"] for row in nodes) == {
        "source": 5,
        "model": 11,
        "exposure": 2,
    }

    owners = yaml.safe_load(
        (PROJECT_DIR / "knowledge" / "owners.yaml").read_text(encoding="utf-8")
    )
    manifest = json.loads((GREEN / "manifest.json").read_text(encoding="utf-8"))
    for row in nodes:
        assert row["owner"] == owners[row["unique_id"]]
        assert row["description"]
        assert row["path"] and "\\" not in row["path"]
        if row["resource_type"] == "model":
            assert row["checksum"] == manifest["nodes"][row["unique_id"]]["checksum"]["checksum"]
            assert row["schema"]
        elif row["resource_type"] == "exposure":
            assert row["checksum"] is None
            assert row["schema"] is None
        else:
            assert row["checksum"] is None
            assert row["schema"]

    ids = {row["unique_id"] for row in nodes}
    assert {(row["parent"], row["child"]) for row in tables["edges"]} == EXPECTED_EDGES
    for parent, child in EXPECTED_EDGES:
        assert parent in ids and child in ids
    assert not any(
        row["parent"].startswith("test.") or row["child"].startswith("test.")
        for row in tables["edges"]
    )

    by_name = {row["name"]: row for row in tables["exposures"]}
    assert set(by_name) == {"finance_dashboard", "collections_report"}
    assert by_name["finance_dashboard"]["depends_on"] == [
        "model.billing_mart.fct_revenue_daily",
        "model.billing_mart.mrr_monthly",
    ]
    assert by_name["collections_report"]["depends_on"] == [
        "model.billing_mart.dim_accounts"
    ]


def test_green_tests_store_every_model_they_depend_on():
    tables = load_tables(GREEN)
    tests = tables["tests"]
    # 73 tests. Five relationships tests and two singular tests each depend
    # on two models, so those seven add an extra row. The other singular
    # tests, including assert_plan_prices_in_range, depend on one model.
    assert len({row["unique_id"] for row in tests}) == 73
    assert len(tests) == 80
    assert {row["severity"] for row in tests} == {"error", "warn"}
    assert {row["test_type"] for row in tests if row["severity"] == "warn"} == {
        "not_null",
        "accepted_values",
    }
    assert sum(1 for row in tests if row["severity"] == "warn") == 21

    for name in (
        "assert_revenue_reconciles_to_payments",
        "assert_billed_reconciles_to_invoices",
    ):
        rows = [row for row in tests if row["test_type"] == name]
        assert len(rows) == 2
        assert all(row["column"] is None and row["severity"] == "error" for row in rows)

    revenue = {
        row["attached_node"]
        for row in tests
        if row["test_type"] == "assert_revenue_reconciles_to_payments"
    }
    assert revenue == {
        "model.billing_mart.fct_revenue_daily",
        "model.billing_mart.stg_payments__payments",
    }

    invoice_fk = {
        row["attached_node"]
        for row in tests
        if row["test_type"] == "relationships" and row["column"] == "invoice_id"
    }
    assert invoice_fk == {
        "model.billing_mart.stg_billing__invoices",
        "model.billing_mart.stg_payments__payments",
    }

    mrr = [row for row in tests if row["test_type"] == "assert_mrr_non_negative"]
    assert len(mrr) == 1
    assert mrr[0]["attached_node"] == "model.billing_mart.mrr_monthly"

    prices = [row for row in tests if row["test_type"] == "assert_plan_prices_in_range"]
    assert len(prices) == 1
    assert prices[0]["attached_node"] == "model.billing_mart.int_subscription_periods"
    assert prices[0]["column"] is None
    assert prices[0]["severity"] == "error"


def test_green_columns_take_types_from_the_catalog_and_pii_from_policy():
    tables = load_tables(GREEN)
    columns = tables["columns"]
    assert len(columns) == 97
    assert all(row["data_type"] for row in columns)

    catalog = json.loads((GREEN / "catalog.json").read_text(encoding="utf-8"))
    catalog_types: dict[tuple[str, str], str] = {}
    for section in ("nodes", "sources"):
        for unique_id, node in catalog[section].items():
            for name, column in node["columns"].items():
                catalog_types[(unique_id, name)] = column["type"]
    for row in columns:
        assert row["data_type"] == catalog_types[(row["unique_id"], row["column"])]

    policy = yaml.safe_load(
        (PROJECT_DIR / "knowledge" / "policy.yaml").read_text(encoding="utf-8")
    )
    tagged = {
        (row["unique_id"], row["column"]): row["pii_tag"]
        for row in columns
        if row["pii_tag"]
    }
    expected = {
        (row["unique_id"], row["column"]): policy[row["column"]]
        for row in columns
        if row["column"] in policy
    }
    assert tagged == expected
    assert len(tagged) == 8


def test_green_results_and_freshness_copy_the_artifact_text():
    tables = load_tables(GREEN)
    run_results = json.loads((GREEN / "run_results.json").read_text(encoding="utf-8"))
    assert [row["unique_id"] for row in tables["results"]] == [
        result["unique_id"] for result in run_results["results"]
    ]
    assert len(tables["results"]) == 86
    for row, result in zip(tables["results"], run_results["results"], strict=True):
        assert row["status"] == result["status"]
        assert row["message"] == result["message"]
        if result["failures"] is None:
            assert row["failures"] is None
        else:
            assert row["failures"] == result["failures"]
        if row["resource_type"] == "test":
            assert row["severity"] in {"error", "warn"}
        else:
            assert row["severity"] is None

    assert {row["status"] for row in tables["results"] if row["resource_type"] == "model"} == {
        "success"
    }
    assert {row["status"] for row in tables["results"] if row["resource_type"] == "test"} == {
        "pass"
    }
    assert {
        row["status"] for row in tables["results"] if row["resource_type"] == "exposure"
    } == {"no-op"}

    sources = json.loads((GREEN / "sources.json").read_text(encoding="utf-8"))
    by_id = {row["unique_id"]: row for row in tables["freshness"]}
    assert set(by_id) == {
        "source.billing_mart.crm.accounts",
        "source.billing_mart.payments.payments",
    }
    for result in sources["results"]:
        row = by_id[result["unique_id"]]
        assert row["status"] == result["status"]
        assert row["max_loaded_at"] == result["max_loaded_at"]
        assert row["snapshotted_at"] == result["snapshotted_at"]
        assert row["warn_after"] == "12 hour"
        assert row["error_after"] == "24 hour"


def test_harvest_writes_meta_duckdb_and_replaces_it(tmp_path: Path):
    _copy_green(tmp_path)
    counts = harvest(tmp_path)
    assert counts == {
        "nodes": 18,
        "columns": 97,
        "edges": 18,
        "tests": 80,
        "exposures": 2,
        "results": 86,
        "freshness": 2,
    }
    database = tmp_path / "meta.duckdb"
    assert database.is_file()

    connection = duckdb.connect(str(database), read_only=True)
    try:
        columns = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tests'
            ORDER BY ordinal_position
            """
        ).fetchall()
        assert [row[0] for row in columns] == [
            "unique_id",
            "attached_node",
            "column",
            "test_type",
            "severity",
        ]
        owner, checksum, schema = connection.execute(
            """
            SELECT owner, checksum, "schema"
            FROM nodes
            WHERE unique_id = 'model.billing_mart.fct_revenue_daily'
            """
        ).fetchone()
        assert owner == "finance-data"
        assert checksum and len(checksum) == 64
        assert schema == "marts"
        tags = connection.execute(
            """
            SELECT tags FROM nodes
            WHERE unique_id = 'source.billing_mart.payments.payments'
            """
        ).fetchone()[0]
        assert list(tags) == []
        depends = connection.execute(
            """
            SELECT depends_on FROM exposures WHERE name = 'finance_dashboard'
            """
        ).fetchone()[0]
        assert list(depends) == [
            "model.billing_mart.fct_revenue_daily",
            "model.billing_mart.mrr_monthly",
        ]
        pii = connection.execute(
            """
            SELECT pii_tag FROM columns
            WHERE unique_id = 'model.billing_mart.dim_accounts' AND "column" = 'contact_email'
            """
        ).fetchone()[0]
        assert pii == "email"
    finally:
        connection.close()

    assert harvest(tmp_path) == counts


def test_main_prints_a_count_for_every_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _copy_green(tmp_path)
    assert main([str(tmp_path)]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [line.split()[0] for line in lines] == list(TABLE_NAMES)
    tables = load_tables(tmp_path)
    for line, name in zip(lines, TABLE_NAMES, strict=True):
        assert int(line.split()[1]) == len(tables[name])


def test_missing_artifact_names_the_file(tmp_path: Path):
    with pytest.raises(HarvestError, match="not found"):
        load_tables(tmp_path / "nope")
    with pytest.raises(HarvestError, match="manifest.json"):
        load_tables(tmp_path)
    assert main([]) == 2
