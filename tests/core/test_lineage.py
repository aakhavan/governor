"""Lineage closures on a hand-made graph and on the green manifest."""

from __future__ import annotations

from collections import defaultdict

import pytest

from triage.config import PROJECT_DIR
from triage.harvest import as_graph, load_tables
from triage.lineage import (
    descendants,
    downstream,
    failing_nodes,
    root_failures,
    topological_order,
    upstream,
)

# source → stg → int_model → mart → exposure, and stg → side.
# Alphabetical tie-break puts exposure before side: after int_model is
# emitted, mart is ready and sorts ahead of side.
GRAPH = {
    "nodes": ["source", "stg", "int_model", "mart", "exposure", "side"],
    "edges": [
        {"parent": "source", "child": "stg"},
        {"parent": "stg", "child": "int_model"},
        {"parent": "stg", "child": "side"},
        {"parent": "int_model", "child": "mart"},
        {"parent": "mart", "child": "exposure"},
    ],
}

ORDER = ["source", "stg", "int_model", "mart", "exposure", "side"]

GREEN = PROJECT_DIR / "artifacts" / "green"
PAYMENTS = "source.billing_mart.payments.payments"
INT_PAYMENTS = "model.billing_mart.int_payments_with_accounts"
FCT_REVENUE = "model.billing_mart.fct_revenue_daily"


def test_closures_respect_depth_and_include_the_exposure():
    assert topological_order(GRAPH) == ORDER

    assert upstream("mart", GRAPH, 0) == []
    assert upstream("mart", GRAPH, 1) == ["int_model"]
    assert upstream("mart", GRAPH, 2) == ["stg", "int_model"]
    assert upstream("exposure", GRAPH, 10) == ["source", "stg", "int_model", "mart"]
    assert upstream("missing", GRAPH, 5) == []

    assert downstream("stg", GRAPH, 1) == ["int_model", "side"]
    assert downstream("source", GRAPH, 2) == ["stg", "int_model", "side"]
    assert descendants("source", GRAPH) == [
        "stg",
        "int_model",
        "mart",
        "exposure",
        "side",
    ]
    assert "source" not in descendants("source", GRAPH)
    assert descendants("exposure", GRAPH) == []
    assert longest_source_exposure_hops(GRAPH, ["source"], ["exposure"]) == 4


def test_diamond_keeps_both_parents_inside_the_depth_limit():
    diamond = {
        "nodes": ["a", "b", "c", "d"],
        "edges": [
            {"parent": "a", "child": "b"},
            {"parent": "a", "child": "c"},
            {"parent": "b", "child": "d"},
            {"parent": "c", "child": "d"},
        ],
    }
    assert downstream("a", diamond, 1) == ["b", "c"]
    assert downstream("a", diamond, 2) == ["b", "c", "d"]
    assert upstream("d", diamond, 1) == ["b", "c"]
    assert upstream("d", diamond, 2) == ["a", "b", "c"]


def test_root_failures_keeps_nodes_with_no_failing_ancestor():
    assert root_failures(["mart", "int_model"], GRAPH) == ["int_model"]
    assert root_failures(["exposure", "stg"], GRAPH) == ["stg"]
    assert root_failures(["side", "mart"], GRAPH) == ["mart", "side"]
    assert root_failures(["exposure"], GRAPH) == ["exposure"]
    assert root_failures(["int_model", "int_model", "mart"], GRAPH) == ["int_model"]
    assert root_failures([], GRAPH) == []
    # Ids outside the graph have no ancestor. They follow the graph nodes.
    assert root_failures(["zzz", "side", "aaa", "side"], GRAPH) == ["side", "aaa", "zzz"]

    alone = {"nodes": ["alone"], "edges": []}
    assert topological_order(alone) == ["alone"]
    assert upstream("alone", alone, 3) == []
    assert descendants("alone", alone) == []
    assert root_failures(["alone"], alone) == ["alone"]


def test_failing_nodes_maps_error_level_results_and_drops_warns():
    tables = load_tables(GREEN)
    graph = as_graph(tables)
    tests = tables["tests"]

    def one(fragment: str) -> str:
        matches = {row["unique_id"] for row in tests if fragment in row["unique_id"]}
        assert len(matches) == 1, matches
        return next(iter(matches))

    revenue = one("assert_revenue_reconciles_to_payments")
    billed = one("assert_billed_reconciles_to_invoices")
    created = one("not_null_stg_crm__accounts_created_at")
    results = [
        {
            "unique_id": revenue,
            "resource_type": "test",
            "status": "fail",
            "severity": "error",
        },
        {
            "unique_id": created,
            "resource_type": "test",
            "status": "error",
            "severity": "warn",
        },
        {
            "unique_id": "model.billing_mart.mrr_monthly",
            "resource_type": "model",
            "status": "error",
            "severity": None,
        },
        {
            "unique_id": FCT_REVENUE,
            "resource_type": "model",
            "status": "success",
            "severity": None,
        },
    ]
    freshness = [
        {"unique_id": PAYMENTS, "status": "error"},
        {"unique_id": "source.billing_mart.crm.accounts", "status": "warn"},
    ]
    assert set(failing_nodes(results, tests, graph, freshness)) == {
        FCT_REVENUE,
        "model.billing_mart.mrr_monthly",
        PAYMENTS,
    }
    # The billed test also names the staging model. The mart is downstream.
    assert failing_nodes(
        [
            {
                "unique_id": billed,
                "resource_type": "test",
                "status": "fail",
                "severity": "ERROR",
            }
        ],
        tests,
        graph,
    ) == ["model.billing_mart.dim_accounts"]


def test_failing_nodes_tie_break_uses_the_primary_model():
    graph = {"nodes": ["a", "b"], "edges": []}
    tests = [
        {"unique_id": "t", "attached_node": "a", "primary": True},
        {"unique_id": "t", "attached_node": "b", "primary": False},
    ]
    results = [
        {"unique_id": "t", "resource_type": "test", "status": "fail", "severity": "error"}
    ]
    assert failing_nodes(results, tests, graph) == ["a"]

    untagged = [
        {"unique_id": "t", "attached_node": "a"},
        {"unique_id": "t", "attached_node": "b"},
    ]
    assert failing_nodes(results, untagged, graph) == ["b"]

    with pytest.raises(ValueError, match="does not depend"):
        failing_nodes(results, [], graph)


def test_depth_must_be_a_non_negative_int_and_a_cycle_raises():
    with pytest.raises(ValueError):
        upstream("stg", GRAPH, -1)
    with pytest.raises(TypeError):
        downstream("stg", GRAPH, "1")

    cycle = {
        "nodes": ["a", "b"],
        "edges": [
            {"parent": "a", "child": "b"},
            {"parent": "b", "child": "a"},
        ],
    }
    with pytest.raises(ValueError, match="cycle"):
        topological_order(cycle)


def test_green_manifest_descendants_path_and_root_failures():
    tables = load_tables(GREEN)
    graph = as_graph(tables)

    expected = {
        "model.billing_mart.stg_payments__payments",
        "model.billing_mart.int_invoices_with_payments",
        "model.billing_mart.int_payments_with_accounts",
        "model.billing_mart.dim_accounts",
        "model.billing_mart.fct_revenue_daily",
        "exposure.billing_mart.collections_report",
        "exposure.billing_mart.finance_dashboard",
    }
    order = topological_order(graph)
    assert descendants(PAYMENTS, graph) == sorted(expected, key=order.index)

    sources = [row["unique_id"] for row in tables["nodes"] if row["resource_type"] == "source"]
    exposures = [
        row["unique_id"] for row in tables["nodes"] if row["resource_type"] == "exposure"
    ]
    assert longest_source_exposure_hops(graph, sources, exposures) == 4

    # The int model is the root even though the mart's direct parent is that
    # int model and both ids were passed with the mart first.
    assert root_failures([FCT_REVENUE, INT_PAYMENTS], graph) == [INT_PAYMENTS]
    assert root_failures([FCT_REVENUE], graph) == [FCT_REVENUE]


def longest_source_exposure_hops(
    graph: dict,
    sources: list[str],
    exposures: list[str],
) -> int:
    """Hop count of the longest source → exposure path. An exposure ends the path."""
    children: dict[str, set[str]] = defaultdict(set)
    for edge in graph["edges"]:
        children[edge["parent"]].add(edge["child"])
    ends = set(exposures)
    memo: dict[str, int | None] = {}
    stack: set[str] = set()

    def farthest(unique_id: str) -> int | None:
        if unique_id in memo:
            return memo[unique_id]
        if unique_id in ends:
            memo[unique_id] = 0
            return 0
        if unique_id in stack:
            raise AssertionError(f"cycle at {unique_id}")
        stack.add(unique_id)
        best: int | None = None
        try:
            for child in children.get(unique_id, ()):
                child_hops = farthest(child)
                if child_hops is None:
                    continue
                hops = child_hops + 1
                if best is None or hops > best:
                    best = hops
        finally:
            stack.remove(unique_id)
        memo[unique_id] = best
        return best

    best = 0
    reached = False
    for source in sources:
        hops = farthest(source)
        if hops is None:
            continue
        reached = True
        if hops > best:
            best = hops
    if not reached:
        return 0
    return best
