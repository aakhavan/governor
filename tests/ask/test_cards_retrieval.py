"""Catalog cards from a small fake meta store, tokenisation, RRF order, HashEmbedder."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
import yaml

from governor.ask.catalog import build_cards, sql_tables
from governor.ask.retrieval import HashEmbedder, fuse, search, tokens

METRICS = {
    "version": 1,
    "metrics": [
        {
            "id": "widget_total",
            "label": "Widget total",
            "definition": "Sum of widgets shipped.",
            "sql": "WITH w AS (SELECT qty FROM fct_widgets) SELECT SUM(qty) FROM w",
            "grain": "snapshot",
            "synonyms": ["widgets shipped"],
        },
        {
            "id": "gadget_rate",
            "label": "Gadget rate",
            "definition": "Gadgets per customer.",
            "sql": "SELECT COUNT(*) FROM marts.fct_widgets JOIN dim_customers USING (customer_id)",
            "grain": "month",
            "synonyms": ["gadgets per customer"],
        },
    ],
}


@pytest.fixture()
def store(tmp_path: Path) -> dict[str, Path]:
    meta = tmp_path / "meta.duckdb"
    con = duckdb.connect(str(meta))
    con.execute(
        'create table nodes (unique_id varchar, resource_type varchar, name varchar, "schema" varchar, '
        "owner varchar, description varchar)"
    )
    con.execute(
        'create table columns (unique_id varchar, "column" varchar, data_type varchar, '
        "description varchar, pii_tag varchar)"
    )
    con.execute(
        'create table tests (attached_node varchar, "column" varchar, test_type varchar, severity varchar)'
    )
    con.execute("create table edges (parent varchar, child varchar)")
    con.executemany(
        "insert into nodes values (?, ?, ?, ?, ?, ?)",
        [
            ("source.p.shop.raw_widgets", "source", "raw_widgets", "raw", None, "Raw widgets."),
            ("model.p.stg_widgets", "model", "stg_widgets", "staging", "ops", "Staged widgets."),
            ("model.p.fct_widgets", "model", "fct_widgets", "marts", "ops", "One row per widget, shipped."),
            ("model.p.dim_customers", "model", "dim_customers", "marts", "sales", "Customers."),
        ],
    )
    con.executemany(
        "insert into columns values (?, ?, ?, ?, ?)",
        [
            ("model.p.fct_widgets", "widget_id", "VARCHAR", "Primary key.", None),
            ("model.p.fct_widgets", "shipped_qty", "BIGINT", "Units shipped.", None),
            ("model.p.dim_customers", "customer_id", "VARCHAR", "Primary key.", None),
            ("model.p.dim_customers", "customer_email", "VARCHAR", "Email.", "email"),
        ],
    )
    con.executemany(
        "insert into tests values (?, ?, ?, ?)",
        [("model.p.fct_widgets", "widget_id", "unique", "error"), ("model.p.dim_customers", "customer_id", "unique", "error")],
    )
    con.executemany(
        "insert into edges values (?, ?)",
        [("source.p.shop.raw_widgets", "model.p.stg_widgets"), ("model.p.stg_widgets", "model.p.fct_widgets")],
    )
    con.close()
    metrics = tmp_path / "metrics.yaml"
    metrics.write_text(yaml.safe_dump(METRICS), encoding="utf-8")
    access = tmp_path / "access.yaml"
    access.write_text(yaml.safe_dump({"allowlist": {"models": ["fct_widgets", "dim_customers"]}}), encoding="utf-8")
    return {"meta_path": meta, "metrics_path": metrics, "access_path": access}


def test_cards_from_fake_meta_store(store):
    cards = build_cards(**store)
    by_id = {c["id"]: c for c in cards}
    assert list(by_id) == ["model:fct_widgets", "model:dim_customers", "metric:widget_total", "metric:gadget_rate"]
    for card in cards:
        assert {"id", "kind", "name", "text", "tables", "pii_columns"} <= set(card)
    widgets = by_id["model:fct_widgets"]
    assert widgets["kind"] == "model" and widgets["tables"] == ["fct_widgets"]
    assert "shipped_qty (BIGINT): Units shipped." in widgets["text"]
    assert "grain: One row per widget" in widgets["text"]
    assert "owner: ops" in widgets["text"]
    assert "unique on widget_id" in widgets["text"]
    assert "upstream sources: shop.raw_widgets" in widgets["text"]
    assert "widget_total (Widget total)" in widgets["text"]
    assert widgets["pii_columns"] == []
    customers = by_id["model:dim_customers"]
    assert customers["pii_columns"] == ["customer_email"]
    assert "customer_email (VARCHAR) pii:email" in customers["text"]
    assert "grain: one row per customer_id" in customers["text"]
    assert "stg_widgets" not in {c["name"] for c in cards}
    assert by_id["metric:widget_total"]["tables"] == ["fct_widgets"]
    assert by_id["metric:gadget_rate"]["tables"] == ["dim_customers", "fct_widgets"]
    assert "widgets shipped" in by_id["metric:widget_total"]["text"]


def test_allowlisted_model_missing_from_meta_fails(store):
    store["access_path"].write_text(yaml.safe_dump({"allowlist": {"models": ["nope"]}}), encoding="utf-8")
    with pytest.raises(ValueError, match="nope"):
        build_cards(**store)


def test_sql_tables_drops_ctes_and_schema():
    assert sql_tables("WITH t AS (SELECT 1 FROM marts.a) SELECT * FROM t JOIN b ON TRUE") == ["a", "b"]


def test_tokens_split_snake_case():
    assert tokens("Days_Outstanding > 30") == ["days_outstanding", "days", "outstanding", "30"]
    assert tokens("mrr") == ["mrr"]


def test_bm25_matches_snake_case_parts(store):
    cards = build_cards(**store)
    hits = search("units shipped qty", k=1, mode="bm25", cards=cards)
    assert hits[0].card_id == "model:fct_widgets"
    assert hits[0].tables == ["fct_widgets"]


def test_rrf_order_on_fixed_example():
    a, b, c, d = ({"id": x, "name": x} for x in "abcd")
    fused = fuse([[a, b, c], [c, a, d]])
    assert [card["id"] for card, _ in fused] == ["a", "c", "b", "d"]
    scores = dict((card["id"], score) for card, score in fused)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert scores["b"] == pytest.approx(1 / 62)
    assert scores["d"] == pytest.approx(1 / 63)


def test_hash_embedder_is_deterministic():
    one, two = HashEmbedder(), HashEmbedder()
    assert one.embed_query("monthly revenue") == two.embed_query("monthly revenue")
    assert one.embed_documents(["a b", "c"]) == [two.embed_query("a b"), two.embed_query("c")]
    assert one.embed_query("monthly revenue") != one.embed_query("open invoices")
    assert len(one.embed_query("x")) == 256
    assert one.embed_query("") == [0.0] * 256


def test_hybrid_and_dense_with_cached_embeddings(store, tmp_path):
    cards = build_cards(**store)
    cache = tmp_path / "emb.npz"
    first = search("widgets shipped", k=2, mode="hybrid", embedder="fake", cards=cards, cache=cache)
    assert cache.is_file() and len(first) == 2
    again = search("widgets shipped", k=2, mode="hybrid", embedder=HashEmbedder(), cards=cards, cache=cache)
    assert again == first
    dense = search("customer email", k=4, mode="dense", embedder="fake", cards=cards, cache=cache)
    assert len(dense) == 4
    changed = [dict(c, text=c["text"] + " extra") for c in cards]
    search("x", k=1, mode="dense", embedder="fake", cards=changed, cache=cache)
    assert search("widgets shipped", k=2, mode="hybrid", embedder="fake", cards=cards, cache=cache) == first
