"""Profile a raw schema (batch2.md section 5). Deterministic, no model calls.

All work is aggregates on the server: Python only ever receives counts, and min/max for non-PII
integer, numeric, timestamp and date columns. A PII value is never fetched.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path

import psycopg
import yaml
from psycopg import sql

from governor.build.models import ColumnProfile, Profile, Relationship, TableProfile
from governor.core.pgconn import with_timeout

# One set of patterns for the server (Postgres ARE) and the offline check (Python re). No backslashes,
# so the literals need no escaping. Leading zeros make a value a code (zip prefixes), not a number.
_INT = "[+-]?(0|[1-9][0-9]*)"
PATTERNS: dict[str, str] = {
    "boolean": "^(true|false|t|f)$",  # case-insensitive
    "integer": f"^{_INT}$",
    "numeric": f"^([+-]?(0|[1-9][0-9]*)([.][0-9]*)?|[+-]?[.][0-9]+)([eE][+-]?[0-9]+)?$",
    "date": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
    "timestamp": "^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T][0-9]{2}:[0-9]{2}(:[0-9]{2}([.][0-9]+)?)?(Z|[+-][0-9]{2}(:?[0-9]{2})?)?)?$",
}
# First type whose pattern every non-null value matches wins; integers also match numeric, dates also match timestamp.
TYPE_ORDER = ("boolean", "integer", "numeric", "date", "timestamp")
_CASTS = {"integer": "numeric", "numeric": "numeric", "date": "date", "timestamp": "timestamp"}
RELATIONSHIP_MIN_COVERAGE = 0.95
_COMPILED = {t: re.compile(p, re.IGNORECASE if t == "boolean" else 0) for t, p in PATTERNS.items()}


def infer_type(values: Iterable[str | None]) -> str:
    """The inferred type of raw text values (empty and blank strings count as null); the same rule the SQL applies."""
    present = [v.strip() for v in values if v is not None and v.strip()]
    if not present:
        return "text"
    for t in TYPE_ORDER:
        if all(_COMPILED[t].match(v) for v in present):
            return t
    return "text"


def load_policy(path: str | Path) -> dict[str, str]:
    """Column -> PII tag from a policy file (``knowledge/shop/policy.yaml`` format)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"policy file {path} is not a mapping of column to tag")
    return {str(k): str(v) for k, v in data.items()}


def _value(col: str) -> sql.Composable:
    return sql.SQL("nullif(btrim({}::text), '')").format(sql.Identifier(col))


def _tables(conn: psycopg.Connection, schema: str) -> dict[str, list[str]]:
    rows = conn.execute(
        "select c.table_name, c.column_name from information_schema.columns c "
        "join information_schema.tables t using (table_schema, table_name) "
        "where c.table_schema = %s and t.table_type = 'BASE TABLE' "
        "order by c.table_name, c.ordinal_position",
        (schema,),
    ).fetchall()
    tables: dict[str, list[str]] = {}
    for table, column in rows:
        cols = tables.setdefault(table, [])
        if not column.startswith("_"):
            cols.append(column)
    return dict(sorted(tables.items()))


def _match(v: sql.Composable, t: str) -> sql.Composable:
    op = sql.SQL("~*" if t == "boolean" else "~")
    return sql.SQL("count(*) filter (where {} {} {})").format(v, op, sql.Literal(PATTERNS[t]))


def _scan(conn: psycopg.Connection, rel: sql.Composable, cols: list[str], checks: list[tuple[str, ...]],
          limit: int | None) -> tuple[int, list[tuple[int, dict[str, int]]]]:
    """One scan (parallel-safe aggregates only): row count, and per column the non-null count and the match
    counts of the patterns in ``checks[i]``."""
    inner = sql.SQL(", ").join(sql.SQL("{} as {}").format(_value(c), sql.Identifier(f"c{i}")) for i, c in enumerate(cols))
    aggs: list[sql.Composable] = [sql.SQL("count(*)")]
    for i, types in enumerate(checks):
        v = sql.Identifier(f"c{i}")
        aggs.append(sql.SQL("count({})").format(v))
        aggs += [_match(v, t) for t in types]
    source = sql.SQL("select {} from {}").format(inner if cols else sql.SQL("1 as one"), rel)
    if limit is not None:
        source = sql.SQL("{} limit {}").format(source, sql.Literal(limit))
    row = conn.execute(sql.SQL("select {} from ({}) s").format(sql.SQL(", ").join(aggs), source)).fetchone()
    out, k = [], 1
    for types in checks:
        out.append((row[k], dict(zip(types, row[k + 1 : k + 1 + len(types)]))))
        k += 1 + len(types)
    return row[0], out


def _distinct(conn: psycopg.Connection, rel: sql.Composable, exprs: list[sql.Composable], limit: int | None = None) -> int:
    """Distinct non-null value (or tuple) count, as a hash aggregate over bytewise (collate "C") text:
    the same count as the database collation, several times faster than ``count(distinct ...)``."""
    cols = sql.SQL(", ").join(sql.SQL('{} collate "C" as {}').format(e, sql.Identifier(f"d{i}")) for i, e in enumerate(exprs))
    source = sql.SQL("select {} from {}").format(cols, rel)
    if limit is not None:
        source = sql.SQL("{} limit {}").format(source, sql.Literal(limit))
    not_null = sql.SQL(" and ").join(sql.SQL("{} is not null").format(sql.Identifier(f"d{i}")) for i in range(len(exprs)))
    query = sql.SQL("select count(*) from (select distinct * from ({}) s) d where {}").format(source, not_null)
    return conn.execute(query).fetchone()[0]


# The types a column can still have once a sample says ``t``: more values only widen it (or make it text).
_WIDER = {"boolean": ("boolean",), "integer": ("integer", "numeric"), "numeric": ("numeric",),
          "date": ("date", "timestamp"), "timestamp": ("timestamp",), "text": ()}
SAMPLE_ROWS = 10_000
PAIR_SAMPLE_ROWS = 100_000


def _stats(conn: psycopg.Connection, rel: sql.Composable, cols: list[str]) -> tuple[int, list[dict]]:
    """Row count, and per column: non-null count, distinct count and inferred type. A sample proposes a type;
    the full scan then checks only that type and its wider ones, so most columns cost one regex, text none."""
    _, sample = _scan(conn, rel, cols, [TYPE_ORDER] * len(cols), SAMPLE_ROWS)
    checks = [_WIDER[_type_from_counts(n, m)] if n else TYPE_ORDER for n, m in sample]
    rows, full = _scan(conn, rel, cols, checks, None)
    return rows, [
        {"nonnull": n, "distinct": _distinct(conn, rel, [_value(c)]) if n else 0, "type": _type_from_counts(n, m)}
        for c, (n, m) in zip(cols, full)
    ]


def _type_from_counts(nonnull: int, matches: dict[str, int]) -> str:
    if nonnull == 0:
        return "text"
    return next((t for t in TYPE_ORDER if t in matches and matches[t] == nonnull), "text")


def _json_value(kind: str, v):
    if v is None:
        return None
    if kind == "integer":
        return int(v)
    if kind == "numeric":
        return float(v)
    return v.isoformat(sep=" ") if kind == "timestamp" else v.isoformat()


def _min_max(conn: psycopg.Connection, rel: sql.Composable, cols: dict[str, str]) -> dict[str, tuple | None]:
    """min/max per column (name -> type). A column whose values pass the pattern but not the cast gets None."""
    if not cols:
        return {}

    def query(names: list[str]) -> sql.Composable:
        parts = []
        for c in names:
            cast = sql.SQL("{}::{}").format(_value(c), sql.SQL(_CASTS[cols[c]]))
            parts += [sql.SQL("min({})").format(cast), sql.SQL("max({})").format(cast)]
        return sql.SQL("select {} from {}").format(sql.SQL(", ").join(parts), rel)

    names = list(cols)
    try:
        row = conn.execute(query(names)).fetchone()
        return {c: (_json_value(cols[c], row[2 * i]), _json_value(cols[c], row[2 * i + 1])) for i, c in enumerate(names)}
    except psycopg.errors.DataError:
        pass
    out: dict[str, tuple | None] = {}
    for c in names:  # one bad column: find it, keep the rest
        try:
            lo, hi = conn.execute(query([c])).fetchone()
            out[c] = (_json_value(cols[c], lo), _json_value(cols[c], hi))
        except psycopg.errors.DataError:
            out[c] = None
    return out


def _pair_keys(conn: psycopg.Connection, rel: sql.Composable, rows: int, columns: list[ColumnProfile]) -> list[list[str]]:
    """Column pairs with no nulls that are unique together. A duplicate in the first rows already rules a pair out."""
    full = [c for c in columns if c.null_rate == 0.0]
    keys = []
    for a, b in combinations(full, 2):
        if a.distinct * b.distinct < rows:
            continue
        exprs = [_value(a.name), _value(b.name)]
        if rows > PAIR_SAMPLE_ROWS and _distinct(conn, rel, exprs, PAIR_SAMPLE_ROWS) < PAIR_SAMPLE_ROWS:
            continue
        if _distinct(conn, rel, exprs) == rows:
            keys.append([a.name, b.name])
    return keys


def _coverage(conn: psycopg.Connection, schema: str, key_table: str, other: str, col: str) -> float | None:
    """Share of ``other.col``'s non-null distinct values found in ``key_table.col``; None when it has none."""
    v = _value(col)
    query = sql.SQL(
        "select count(*), count(k.v) from (select distinct {v} as v from {o}) u "
        "left join (select distinct {v} as v from {t}) k on k.v = u.v where u.v is not null"
    ).format(v=v, o=sql.Identifier(schema, other), t=sql.Identifier(schema, key_table))
    total, found = conn.execute(query).fetchone()
    return found / total if total else None


def profile_schema(dsn: str, schema: str = "raw", policy: dict[str, str] | None = None) -> dict:
    """Profile every base table of ``schema`` (section 5 structure)."""
    policy = policy or {}
    tables: list[TableProfile] = []
    with psycopg.connect(with_timeout(dsn), autocommit=True) as conn:
        conn.read_only = True
        conn.execute("set work_mem = '128MB'")  # distinct counts hash in memory; this session only
        layout = _tables(conn, schema)
        for name, cols in layout.items():
            rel = sql.Identifier(schema, name)
            rows, stats = _stats(conn, rel, cols)
            kinds = {c: s["type"] for c, s in zip(cols, stats)}
            pii = {c: c in policy or f"{name}.{c}" in policy for c in cols}
            ranged = {c: k for c, k in kinds.items() if k in _CASTS and not pii[c]}
            bounds = _min_max(conn, rel, ranged)
            columns = []
            for c, s in zip(cols, stats):
                kind = kinds[c]
                if c in bounds and bounds[c] is None:
                    kind = "text"  # matched the pattern but not the cast (e.g. 2026-02-30)
                lo, hi = bounds.get(c) or (None, None)
                columns.append(ColumnProfile(
                    name=c, inferred_type=kind, null_rate=round(1 - s["nonnull"] / rows, 6) if rows else 0.0,
                    distinct=s["distinct"], pii=pii[c], min=lo, max=hi,
                ))
            keys = [[c.name] for c in columns if rows and c.null_rate == 0.0 and c.distinct == rows]
            if rows and not keys:
                keys = _pair_keys(conn, rel, rows, columns)
            tables.append(TableProfile(name=name, rows=rows, columns=columns, candidate_keys=keys))

        relationships: list[Relationship] = []
        for t in tables:
            for key in (k[0] for k in t.candidate_keys if len(k) == 1):
                for other in tables:
                    if other.name == t.name or key not in layout[other.name]:
                        continue
                    cov = _coverage(conn, schema, t.name, other.name, key)
                    if cov is not None and cov >= RELATIONSHIP_MIN_COVERAGE:
                        relationships.append(
                            Relationship(from_=f"{other.name}.{key}", to=f"{t.name}.{key}", coverage=round(cov, 4))
                        )
    relationships.sort(key=lambda r: (r.from_, r.to))
    return Profile(schema_=schema, tables=tables, relationships=relationships).to_json_dict()
