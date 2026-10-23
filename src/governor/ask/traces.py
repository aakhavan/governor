"""Decision traces: one row per asked question, in DuckDB under ``paths.STATE``.

``record_trace`` (the last graph node) builds the row with ``TRACE_COLUMNS``
and calls ``write_trace``. This module is the only place that opens the trace
store read-write; every connection is closed after use (Windows file locks).

What is stored:

* The question as its sha256 and length. The text itself goes into the extra
  ``question_text`` column only when ``GOVERNOR_TRACE_TEXT=1``.
* Never a raw PII value. Result cells from PII-tagged columns (granted or
  not) and anything that looks like an email address are replaced by the
  policy mask before the row is written, in every text field. Masked results
  already hold the mask (the executor masks inside DuckDB).
* List and dict fields (``retrieved_ids``, ``sql_attempts``,
  ``policy_decisions``, ``models``) as JSON text; ``get_trace`` and
  ``list_traces`` decode them again.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import duckdb
import yaml

from governor.ask.schemas import TRACE_COLUMNS
from governor.core import paths

TABLE = "traces"
TEXT_ENV = "GOVERNOR_TRACE_TEXT"
EXTRA_COLUMNS = ("question_text",)
JSON_COLUMNS = frozenset({"retrieved_ids", "sql_attempts", "policy_decisions", "models"})
_TYPES = {
    "trace_id": "VARCHAR PRIMARY KEY",
    "question_len": "INTEGER",
    "row_count": "BIGINT",
    "tokens_in": "BIGINT",
    "tokens_out": "BIGINT",
    "cost_usd": "DOUBLE",
    "latency_s": "DOUBLE",
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# Fields that may echo result values or literals; the rest are ids, hashes and numbers.
_SCRUBBED = ("answer", "executed_sql", "sql_attempts", "plan_json", "question_text")


def _path(path: Path | str | None) -> Path:
    return Path(path) if path is not None else paths.TRACES


def default_mask(access_path: Path | None = None) -> str:
    """The policy mask value from access.yaml."""
    access = yaml.safe_load(Path(access_path or paths.KNOWLEDGE / "access.yaml").read_text(encoding="utf-8"))
    return str(access["mask_value"])


def pii_values(
    sql: str | None,
    columns: list[str],
    rows: list[list[Any]],
    *,
    access_path: Path | None = None,
    meta_path: Path | None = None,
) -> set[str]:
    """String cells of the result columns that trace back to a PII-tagged column."""
    if not sql or not rows:
        return set()
    from governor.eval.pii import load_policy, output_lineage

    policy = load_policy(Path(meta_path) if meta_path else None, Path(access_path) if access_path else None)
    lineage = output_lineage(sql, policy)
    if lineage is None:  # untraceable: judge by column name
        lineage = [{o for o in policy.pii if o[1] == str(name).lower()} for name in columns]
    out = set()
    for i, origins in enumerate(lineage):
        if not origins:
            continue
        for row in rows:
            value = row[i] if i < len(row) else None
            if isinstance(value, str) and value != policy.mask_value and len(value.strip()) >= 2:
                out.add(value)
    return out


def redact(text: str | None, secrets: Iterable[str], mask: str) -> str | None:
    """``text`` with every secret value and every email-like string replaced by ``mask``."""
    if text is None:
        return None
    for value in sorted(set(secrets), key=len, reverse=True):
        text = re.sub(r"(?<!\w)" + re.escape(value) + r"(?!\w)", mask, text, flags=re.IGNORECASE)
    return EMAIL.sub(mask, text)


def store_text() -> bool:
    return os.environ.get(TEXT_ENV) == "1"


def _encode(row: dict, secrets: Iterable[str], mask: str) -> list[Any]:
    secrets = list(secrets)
    values = []
    for column in TRACE_COLUMNS + EXTRA_COLUMNS:
        value = row.get(column)
        if column in JSON_COLUMNS:
            value = json.dumps(value if value is not None else [], default=str, sort_keys=True)
        if column in _SCRUBBED and value is not None:
            value = redact(str(value), secrets, mask)
        values.append(value)
    return values


def _decode(names: list[str], values: tuple) -> dict:
    row = dict(zip(names, values))
    for column in JSON_COLUMNS:
        if isinstance(row.get(column), str):
            row[column] = json.loads(row[column])
    return row


def _ensure(connection: duckdb.DuckDBPyConnection) -> None:
    columns = ", ".join(f"{c} {_TYPES.get(c, 'VARCHAR')}" for c in TRACE_COLUMNS + EXTRA_COLUMNS)
    connection.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} ({columns})")


def write_trace(
    row: dict,
    *,
    question: str | None = None,
    secrets: Iterable[str] = (),
    mask: str | None = None,
    path: Path | str | None = None,
) -> str:
    """Insert one trace row; returns its ``trace_id``.

    ``row`` must have every key in ``TRACE_COLUMNS``. ``question`` is stored
    only when ``GOVERNOR_TRACE_TEXT=1``. ``secrets`` are PII values to mask
    wherever they appear (see ``pii_values``). Raises on any storage error:
    the caller decides whether a failed write matters.
    """
    missing = [c for c in TRACE_COLUMNS if c not in row]
    if missing:
        raise KeyError(f"trace row is missing {missing}")
    full = {**row, "question_text": question if store_text() else None}
    values = _encode(full, secrets, mask if mask is not None else default_mask())
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(target))
    try:
        _ensure(connection)
        marks = ", ".join("?" for _ in values)
        connection.execute(f"INSERT INTO {TABLE} VALUES ({marks})", values)
    finally:
        connection.close()
    return str(row["trace_id"])


def _read(sql: str, params: list[Any], path: Path | str | None) -> list[dict]:
    target = _path(path)
    if not target.is_file():
        return []
    connection = duckdb.connect(str(target), read_only=True)
    try:
        present = connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [TABLE]
        ).fetchone()[0]
        if not present:
            return []
        cursor = connection.execute(sql, params)
        names = [d[0] for d in cursor.description]
        return [_decode(names, r) for r in cursor.fetchall()]
    finally:
        connection.close()


def list_traces(
    role: str | None = None,
    outcome: str | None = None,
    limit: int = 50,
    *,
    path: Path | str | None = None,
) -> list[dict]:
    """Newest traces first, optionally filtered by role and outcome."""
    where, params = [], []
    if role is not None:
        where.append("role = ?")
        params.append(role)
    if outcome is not None:
        where.append("outcome = ?")
        params.append(outcome)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    params.append(int(limit))
    return _read(f"SELECT * FROM {TABLE}{clause} ORDER BY ts DESC LIMIT ?", params, path)


def get_trace(trace_id: str, *, path: Path | str | None = None) -> dict | None:
    rows = _read(f"SELECT * FROM {TABLE} WHERE trace_id = ?", [trace_id], path)
    return rows[0] if rows else None


__all__ = ["TRACE_COLUMNS", "get_trace", "list_traces", "pii_values", "redact", "write_trace"]
