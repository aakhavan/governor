"""Catalog and metric cards for schema retrieval.

One card per allowlisted model (``knowledge/access.yaml``) and one per metric
in ``knowledge/metrics.yaml``. Model cards are built from ``meta.duckdb``
only: description, grain, owner, columns with type, description and PII tag,
tests, and the upstream sources from ``governor.core.lineage``. Metric cards
carry the label, definition, synonyms, grain and the tables their SQL reads
(sqlglot). Nothing is written by hand per table.

Card JSON: ``{id, kind, name, text, tables, pii_columns}``.

    uv run python -m governor.ask.catalog build [--out artifacts/catalog_cards.jsonl]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb
import sqlglot
import yaml
from sqlglot import exp

from governor.core import lineage, paths

CARDS_PATH = paths.ARTIFACTS / "catalog_cards.jsonl"
METRICS_PATH = paths.KNOWLEDGE / "metrics.yaml"
ACCESS_PATH = paths.KNOWLEDGE / "access.yaml"


def sql_tables(sql: str) -> list[str]:
    """Physical tables a query reads, sorted. CTE names and schema prefixes are dropped."""
    tree = sqlglot.parse_one(sql, dialect="duckdb")
    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    names = {table.name.lower() for table in tree.find_all(exp.Table) if table.name}
    return sorted(names - ctes)


def allowlist(access_path: Path = ACCESS_PATH) -> list[str]:
    access = yaml.safe_load(access_path.read_text(encoding="utf-8"))
    return list(access["allowlist"]["models"])


def load_metrics(metrics_path: Path = METRICS_PATH) -> list[dict]:
    return list(yaml.safe_load(metrics_path.read_text(encoding="utf-8"))["metrics"])


def _read_meta(meta_path: Path) -> dict[str, list[tuple]]:
    if not meta_path.is_file():
        raise FileNotFoundError(f"meta.duckdb is missing: {meta_path}")
    connection = duckdb.connect(str(meta_path), read_only=True)
    try:
        return {
            "nodes": connection.execute(
                "select unique_id, resource_type, name, \"schema\", owner, description "
                "from nodes order by unique_id"
            ).fetchall(),
            "columns": connection.execute(
                'select unique_id, "column", data_type, description, pii_tag '
                'from columns order by unique_id, "column"'
            ).fetchall(),
            "tests": connection.execute(
                'select attached_node, "column", test_type, severity '
                'from tests order by attached_node, test_type, "column"'
            ).fetchall(),
            "edges": connection.execute(
                "select parent, child from edges order by parent, child"
            ).fetchall(),
        }
    finally:
        connection.close()


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=\.)\s", text.strip(), maxsplit=1)[0] if text.strip() else ""


def _grain(description: str, tests: list[tuple]) -> str:
    """'One row per ...' from the description, else the column with a unique test."""
    first = _first_sentence(description)
    if first.lower().startswith("one row per"):
        return first.split(",")[0].rstrip(".")
    unique = sorted(column for _node, column, test_type, _sev in tests if test_type == "unique" and column)
    if unique:
        return f"one row per {', '.join(unique)}"
    return "unknown"


def _source_name(unique_id: str) -> str:
    """``source.<project>.<source>.<table>`` -> ``<source>.<table>``."""
    return ".".join(unique_id.split(".")[2:])


def model_cards(meta: dict[str, list[tuple]], models: list[str], metrics: list[dict]) -> list[dict]:
    by_name = {row[2]: row for row in meta["nodes"] if row[1] == "model"}
    kinds = {row[0]: row[1] for row in meta["nodes"]}
    columns: dict[str, list[tuple]] = {}
    for row in meta["columns"]:
        columns.setdefault(row[0], []).append(row)
    tests: dict[str, list[tuple]] = {}
    for row in meta["tests"]:
        tests.setdefault(row[0], []).append(row)
    graph = {
        "nodes": [row[0] for row in meta["nodes"]],
        "edges": [{"parent": p, "child": c} for p, c in meta["edges"]],
    }
    depth = max(len(graph["nodes"]), 1)

    cards: list[dict] = []
    for name in models:
        node = by_name.get(name)
        if node is None:
            raise ValueError(f"allowlisted model {name!r} is not in meta.duckdb")
        unique_id, _kind, _name, schema, owner, description = node
        description = (description or "").strip()
        node_tests = tests.get(unique_id) or []
        sources = [
            _source_name(uid) for uid in lineage.upstream(unique_id, graph, depth) if kinds.get(uid) == "source"
        ]
        used_by = [m for m in metrics if name in sql_tables(m["sql"])]
        pii = [column for _uid, column, _t, _d, tag in columns.get(unique_id) or [] if tag]

        lines = [
            f"model {name} ({schema}.{name})" if schema else f"model {name}",
            f"description: {description or '(none)'}",
            f"grain: {_grain(description, node_tests)}",
            f"owner: {owner or 'unassigned'}",
            "columns:",
        ]
        for _uid, column, data_type, column_description, tag in columns.get(unique_id) or []:
            pii_text = f" pii:{tag}" if tag else ""
            text = (column_description or "").strip()
            lines.append(f"- {column} ({data_type or 'unknown'}){pii_text}: {text}".rstrip(": "))
        if node_tests:
            lines.append("tests:")
            for _node, column, test_type, severity in node_tests:
                lines.append(f"- {test_type} on {column or '(model)'}, severity {severity}")
        if sources:
            lines.append(f"upstream sources: {', '.join(sources)}")
        if used_by:
            lines.append(f"metrics: {', '.join(f'{m['id']} ({m['label']})' for m in used_by)}")
        cards.append(
            {
                "id": f"model:{name}",
                "kind": "model",
                "name": name,
                "text": "\n".join(lines),
                "tables": [name],
                "pii_columns": pii,
            }
        )
    return cards


def metric_cards(metrics: list[dict]) -> list[dict]:
    cards: list[dict] = []
    for metric in metrics:
        tables = sql_tables(metric["sql"])
        lines = [
            f"metric {metric['id']}: {metric['label']}",
            f"definition: {' '.join(str(metric.get('definition') or '').split())}",
            f"synonyms: {', '.join(metric.get('synonyms') or [])}",
            f"grain: {metric.get('grain') or 'unknown'}",
            f"tables: {', '.join(tables)}",
        ]
        if metric.get("time_column"):
            lines.append(f"time column: {metric['time_column']}")
        cards.append(
            {
                "id": f"metric:{metric['id']}",
                "kind": "metric",
                "name": metric["id"],
                "text": "\n".join(lines),
                "tables": tables,
                "pii_columns": [],
            }
        )
    return cards


def build_cards(
    meta_path: Path = paths.META,
    metrics_path: Path = METRICS_PATH,
    access_path: Path = ACCESS_PATH,
) -> list[dict]:
    """Model cards (allowlist order), then metric cards (metrics.yaml order)."""
    metrics = load_metrics(metrics_path)
    meta = _read_meta(meta_path)
    return model_cards(meta, allowlist(access_path), metrics) + metric_cards(metrics)


def write_cards(cards: list[dict], out: Path = CARDS_PATH) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        for card in cards:
            handle.write(json.dumps(card, ensure_ascii=False) + "\n")


def read_cards(path: Path = CARDS_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build catalog and metric cards.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="write one JSON card per line")
    build.add_argument("--out", type=Path, default=CARDS_PATH)
    args = parser.parse_args(argv)
    cards = build_cards()
    write_cards(cards, args.out)
    kinds = {kind: sum(1 for c in cards if c["kind"] == kind) for kind in ("model", "metric")}
    print(json.dumps({"out": str(args.out), "cards": len(cards), **kinds}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
