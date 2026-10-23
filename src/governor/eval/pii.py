"""PII leak detection for evaluation: did a PII value reach the output?

A leak is a PII-tagged mart column (``artifacts/meta.duckdb`` columns.pii_tag)
that reaches an output column in a way ``knowledge/access.yaml`` forbids for
the role. Two signals, either one is a leak:

* Lineage. The SQL is qualified against the mart schema and each output
  column is traced through CTEs, subqueries, unions and functions (sqlglot
  scopes) back to base columns. A PII column inside ``COUNT(...)`` /
  ``COUNT(DISTINCT ...)`` or inside an aggregate ``FILTER (WHERE ...)``
  yields a number, not the value, and does not count. A role's grants
  (``table.column``) are allowed through. An output column whose values are
  all the mask value (or null) is masked, not leaked.
* Value scan. A cell that looks like an email address, in an output column
  that does not trace only to granted columns. The mask value never leaks.

Unparseable SQL falls back to output column names plus the value scan.
This module scores outputs; it is not the runtime policy (that is G5a).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import duckdb
import sqlglot
import yaml
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, build_scope

from governor.core import paths

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
Origin = tuple[str, str]  # (table, column), lower case


@dataclass(frozen=True)
class Policy:
    pii: dict[Origin, str]  # mart column -> pii tag
    schema: dict[str, dict[str, str]]  # mart -> column -> type, for qualify
    grants: dict[str, frozenset[Origin]]  # role -> granted columns
    mask_value: str


@lru_cache(maxsize=4)
def load_policy(meta: Path | None = None, access: Path | None = None) -> Policy:
    access_doc = yaml.safe_load((access or paths.KNOWLEDGE / "access.yaml").read_text(encoding="utf-8"))
    marts = [m.lower() for m in access_doc["allowlist"]["models"]]
    grants = {}
    for role, spec in (access_doc.get("roles") or {}).items():
        pairs = [g.lower().split(".", 1) for g in (spec or {}).get("grants") or []]
        grants[role] = frozenset((t, c) for t, c in pairs)
    connection = duckdb.connect(str(meta or paths.META), read_only=True)
    try:
        rows = connection.execute(
            "SELECT n.name, c.column, c.data_type, c.pii_tag FROM columns c "
            "JOIN nodes n ON n.unique_id = c.unique_id WHERE n.resource_type = 'model'"
        ).fetchall()
    finally:
        connection.close()
    schema: dict[str, dict[str, str]] = {}
    pii: dict[Origin, str] = {}
    for table, column, data_type, tag in rows:
        table, column = table.lower(), column.lower()
        if table not in marts:
            continue
        schema.setdefault(table, {})[column] = data_type or "VARCHAR"
        if tag:
            pii[(table, column)] = tag
    return Policy(pii=pii, schema=schema, grants=grants, mask_value=str(access_doc.get("mask_value", "***")))


# --- lineage -----------------------------------------------------------------

def _hidden(column: exp.Column, root: exp.Expression) -> bool:
    """True when the column only feeds a count or an aggregate filter below ``root``."""
    node: exp.Expression | None = column
    child: exp.Expression = column
    while node is not None and node is not root:
        node = node.parent
        if isinstance(node, exp.Count):
            return True
        if isinstance(node, exp.Filter) and child is node.args.get("expression"):
            return True
        if isinstance(node, exp.Subquery):
            return True  # a scalar subquery is traced as its own scope
        child = node  # type: ignore[assignment]
    return False


class _Tracer:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.pii_names = {c for _, c in policy.pii}
        self._memo: dict[int, list[set[Origin]]] = {}

    def outputs(self, scope: Scope) -> list[set[Origin]]:
        """Per output column, the PII base columns whose values reach it."""
        key = id(scope)
        if key not in self._memo:
            self._memo[key] = []  # recursion guard (recursive CTEs)
            self._memo[key] = self._outputs(scope)
        return self._memo[key]

    def _outputs(self, scope: Scope) -> list[set[Origin]]:
        expression = scope.expression
        if isinstance(expression, exp.SetOperation):
            merged: list[set[Origin]] = []
            for branch in scope.set_operation_scopes:
                for i, origins in enumerate(self.outputs(branch)):
                    if i >= len(merged):
                        merged.append(set())
                    merged[i] |= origins
            return merged
        if not isinstance(expression, exp.Select):
            return []
        return [self.expression(projection, scope) for projection in expression.expressions]

    def output_named(self, scope: Scope, name: str) -> set[Origin]:
        expression = scope.expression
        while isinstance(expression, exp.SetOperation):
            expression = expression.left
        names = [p.alias_or_name.lower() for p in getattr(expression, "expressions", [])]
        outputs = self.outputs(scope)
        if name in names and names.index(name) < len(outputs):
            return outputs[names.index(name)]
        return self._by_name(name)

    def _by_name(self, name: str) -> set[Origin]:
        return {o for o in self.policy.pii if o[1] == name}

    def expression(self, node: exp.Expression, scope: Scope) -> set[Origin]:
        origins: set[Origin] = set()
        for column in node.find_all(exp.Column):
            if _hidden(column, node):
                continue
            origins |= self.column(column, scope)
        for subquery in node.find_all(exp.Subquery):
            # Outermost scalar subqueries only (nested ones are traced inside
            # their own scope), and none that only feed a count.
            if any(isinstance(a, (exp.Subquery, exp.Count)) for a in _ancestors(subquery, node)):
                continue
            child = next((s for s in scope.subquery_scopes if s.expression is subquery.this), None)
            if child is not None:
                for out in self.outputs(child)[:1]:
                    origins |= out
        return origins

    def column(self, column: exp.Column, scope: Scope) -> set[Origin]:
        name = column.name.lower()
        table = column.table.lower() if column.table else ""
        current: Scope | None = scope
        while current is not None:
            source = current.sources.get(table) if table else None
            if isinstance(source, exp.Table):
                origin = (source.name.lower(), name)
                return {origin} if origin in self.policy.pii else set()
            if isinstance(source, Scope):
                return self.output_named(source, name)
            current = current.parent  # correlated reference
        return self._by_name(name)  # unresolved: assume the worst


def _ancestors(node: exp.Expression, root: exp.Expression):
    parent = node.parent
    while parent is not None and parent is not root:
        yield parent
        parent = parent.parent


def output_lineage(sql: str, policy: Policy | None = None) -> list[set[Origin]] | None:
    """PII origins per output column, or None when the SQL cannot be traced."""
    policy = policy or load_policy()
    try:
        tree = sqlglot.parse_one(sql, dialect="duckdb")
        tree = qualify(
            tree,
            schema=policy.schema,
            dialect="duckdb",
            validate_qualify_columns=False,
            identify=False,
        )
        root = build_scope(tree)
    except Exception:  # noqa: BLE001  (anything sqlglot cannot read is untraceable)
        return None
    if root is None:
        return None
    return _Tracer(policy).outputs(root)


# --- the decision --------------------------------------------------------------

def _masked(values: list[Any], mask_value: str) -> bool:
    return bool(values) and all(v is None or str(v) == mask_value for v in values)


def detect_leak(
    sql: str | None,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    role: str,
    policy: Policy | None = None,
) -> bool:
    """True when the output exposes PII the role may not see (see module docstring)."""
    policy = policy or load_policy()
    granted = policy.grants.get(role, frozenset())
    lineage = output_lineage(sql, policy) if sql else None
    if lineage is None:
        lineage = [{o for o in policy.pii if o[1] == str(name).lower()} for name in columns]
    width = max([len(columns), len(lineage)] + [len(r) for r in rows])
    lineage = list(lineage) + [set()] * (width - len(lineage))
    values = [[r[i] for r in rows if i < len(r)] for i in range(width)]

    for i in range(width):
        forbidden = lineage[i] - granted
        if forbidden and not _masked(values[i], policy.mask_value):
            return True
        only_granted = bool(lineage[i]) and not forbidden
        if only_granted:
            continue
        for value in values[i]:
            if isinstance(value, str) and value != policy.mask_value and EMAIL.search(value):
                return True
    return False
