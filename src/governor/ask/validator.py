"""SQL validator: the security boundary between a proposed query and the warehouse.

The model only proposes SQL; this module decides. ``validate`` parses with
sqlglot in the warehouse adapter's dialect, rejects anything outside the role's policy, and on
success returns the SQL to run: LIMIT injected or lowered, and for ``mask``
roles an outer projection that replaces PII values with the mask, so raw PII
never leaves the warehouse.

Checks are default-deny: every relation must be an allowlisted model or a CTE
of the same query, every function in FROM is rejected, and a PII column is
tracked through aliases, CTEs, subqueries and set operations by sqlglot scopes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope

from governor.ask.policy import Policy, UnknownRoleError
from governor.core import adapters
from governor.core.warehouse import MARTS_SCHEMA

# Wall-clock functions. Time must come in as literals derived from as_of.
_VOLATILE_NODES = (
    exp.CurrentDate,
    exp.CurrentDatetime,
    exp.CurrentTime,
    exp.CurrentTimestamp,
    exp.Localtime,
    exp.Localtimestamp,
)
# Names as an anonymous call or a bare column. The CURRENT_* names come from
# sqlglot's own node classes (plus their get_ variants), so this module does
# not spell out the wall-clock functions it forbids.
_NODE_NAMES = {name.lower() for node in _VOLATILE_NODES for name in node.sql_names()}
_VOLATILE_NAMES = (
    _NODE_NAMES
    | {"get_" + name for name in _NODE_NAMES if name.startswith("current_")}
    | {
        "current_localtime",
        "current_localtimestamp",
        "now",
        "statement_timestamp",
        "today",
        "transaction_timestamp",
        "unix_timestamp",
        "epoch_ms_now",
    }
)
# Relations that are table-valued functions however they are spelled.
_TABLE_FUNCTION_NODES = (exp.Unnest, exp.Lateral, exp.Values)


@dataclass
class ValidationResult:
    ok: bool
    codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    sql: str | None = None
    tables: list[str] = field(default_factory=list)
    pii_columns: list[str] = field(default_factory=list)


class _Reject(Exception):
    pass


class _Checks:
    def __init__(self, dialect: str) -> None:
        self.dialect = dialect
        self.codes: list[str] = []
        self.reasons: list[str] = []

    def add(self, code: str, reason: str) -> None:
        if code not in self.codes:
            self.codes.append(code)
        if reason not in self.reasons:
            self.reasons.append(reason)


def validate(
    sql: str,
    role: str,
    *,
    access_path: Path | None = None,
    meta_path: Path | None = None,
    dialect: str | None = None,
) -> ValidationResult:
    """Decide whether ``role`` may run ``sql``; on success return the rewritten SQL.

    SQL is parsed and rendered in ``dialect``, by default the dialect of the
    configured warehouse adapter (``governor.core.adapters.dialect()``).
    """
    checks = _Checks(dialect or adapters.dialect())
    try:
        policy = Policy.for_role(role, access_path=access_path, meta_path=meta_path)
    except UnknownRoleError:
        checks.add("UNKNOWN_ROLE", f"unknown role {role!r}")
        return _fail(checks)
    try:
        return _validate(sql, policy, checks)
    except _Reject:
        return _fail(checks)


def _fail(checks: _Checks, tables: list[str] | None = None) -> ValidationResult:
    return ValidationResult(ok=False, codes=checks.codes, reasons=checks.reasons, tables=tables or [])


def _validate(sql: str, policy: Policy, checks: _Checks) -> ValidationResult:
    tree = _parse(sql, checks)
    _check_relations(tree, policy, checks)
    _check_star(tree, checks)
    _check_volatile(tree, checks)
    if checks.codes:
        raise _Reject
    qualified = _qualify(tree, policy, checks)
    # DuckDB reads a bare relation name as the whole row (a struct of every column).
    for node in qualified.find_all(exp.TableColumn):
        checks.add("STAR", f"whole-row reference {node.name} is not allowed; name the columns")
    if checks.codes:
        raise _Reject
    scopes = _scopes(qualified, checks)
    analysis = _Lineage(scopes, policy, checks.dialect)
    tables = sorted(analysis.tables)
    pii_refs = sorted(analysis.pii_refs)
    if policy.pii_mode == "aggregate_only" and analysis.forbidden:
        for ref in sorted(analysis.forbidden):
            checks.add("PII_FORBIDDEN", f"PII column {ref} used outside COUNT(...) for role {policy.role!r}")
        return _fail(checks, tables)

    masked: list[int] = []
    if policy.pii_mode == "mask":
        masked = analysis.hidden_outputs(scopes[-1])
    out = _apply_limit(tree, policy)
    if masked:
        out = _mask(out, _output_names(tree, checks.dialect), masked, policy)
    return ValidationResult(
        ok=True,
        sql=out.sql(dialect=checks.dialect, comments=False),
        tables=tables,
        pii_columns=pii_refs,
    )


def _parse(sql: str, checks: _Checks) -> exp.Expression:
    if not isinstance(sql, str) or not sql.strip():
        checks.add("PARSE_ERROR", "empty SQL")
        raise _Reject
    try:
        statements = [s for s in sqlglot.parse(sql, read=checks.dialect) if s is not None]
    except (ParseError, SqlglotError) as error:
        checks.add("PARSE_ERROR", f"SQL does not parse: {str(error).splitlines()[0][:200]}")
        raise _Reject from None
    if not statements:
        checks.add("PARSE_ERROR", "no statement")
        raise _Reject
    if len(statements) > 1:
        checks.add("MULTI_STATEMENT", f"{len(statements)} statements; only one SELECT is allowed")
        raise _Reject
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        checks.add("NOT_SELECT", f"{type(tree).__name__} statement; only SELECT or WITH ... SELECT is allowed")
        raise _Reject
    # A SELECT may still embed a write (e.g. a data-modifying CTE).
    for node in tree.walk():
        if isinstance(node, (exp.DML, exp.DDL, exp.Command, exp.Into)) or type(node).__name__ in {
            "Pragma",
            "Attach",
            "Detach",
            "Copy",
            "Set",
            "Install",
            "Use",
        }:
            checks.add("NOT_SELECT", f"{type(node).__name__} inside the query is not allowed")
            raise _Reject
    return tree


def _check_relations(tree: exp.Expression, policy: Policy, checks: _Checks) -> None:
    for node in tree.find_all(*_TABLE_FUNCTION_NODES):
        if isinstance(node, exp.Values) and not isinstance(node.parent, (exp.From, exp.Join, exp.Alias)):
            continue
        checks.add("TABLE_FUNCTION", f"{node.key.upper()} as a relation is not allowed")
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            name = table.this.sql(dialect=checks.dialect)[:80]
            checks.add("TABLE_FUNCTION", f"table function {name} is not allowed")
            continue
        if _looks_like_file(table.name):
            checks.add("TABLE_FUNCTION", f"file read {table.name!r} is not allowed")
    if checks.codes:
        return
    try:
        scopes = traverse_scope(tree)
    except (OptimizeError, SqlglotError) as error:
        checks.add("PARSE_ERROR", f"cannot resolve query scopes: {error}"[:200])
        return
    cte_refs = set()
    for scope in scopes:
        for node, source in scope.selected_sources.values():
            if isinstance(node, exp.Table) and isinstance(source, Scope):
                cte_refs.add(id(node))
    allowed = set(policy.models)
    for table in tree.find_all(exp.Table):
        if id(table) in cte_refs:
            continue
        name = table.name.lower()
        schema = table.db.lower()
        if table.catalog or (schema and schema != MARTS_SCHEMA) or name not in allowed:
            checks.add("TABLE_NOT_ALLOWED", f"relation {table.sql(dialect=checks.dialect)} is not an allowlisted model")


def _looks_like_file(name: str) -> bool:
    return any(ch in name for ch in "./\\:*?") or name.startswith("~")


def _check_star(tree: exp.Expression, checks: _Checks) -> None:
    for star in tree.find_all(exp.Star):
        parent = star.parent
        if isinstance(parent, exp.Count) and parent.this is star:
            continue
        checks.add("STAR", "SELECT * / t.* is not allowed; name the columns")
    for node in tree.find_all(exp.Columns):
        checks.add("STAR", "COLUMNS(...) is not allowed; name the columns")


def _check_volatile(tree: exp.Expression, checks: _Checks) -> None:
    for node in tree.walk():
        if isinstance(node, _VOLATILE_NODES):
            name = node.key
        elif isinstance(node, exp.Func):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if name not in _VOLATILE_NAMES:
                continue
        elif isinstance(node, exp.Column) and not node.table and node.name.lower() in _VOLATILE_NAMES:
            name = node.name
        else:
            continue
        checks.add("VOLATILE_TIME", f"{name} reads the wall clock; use date literals from as_of")


def _qualify(tree: exp.Expression, policy: Policy, checks: _Checks) -> exp.Expression:
    schema = {MARTS_SCHEMA: policy.schema}
    try:
        return qualify(
            tree.copy(),
            dialect=checks.dialect,
            db=MARTS_SCHEMA,
            schema=schema,
            quote_identifiers=False,
            identify=False,
            validate_qualify_columns=True,
        )
    except (OptimizeError, SqlglotError) as error:
        checks.add("COLUMN_UNKNOWN", f"column check failed: {str(error).splitlines()[0][:200]}")
        raise _Reject from None


def _scopes(tree: exp.Expression, checks: _Checks) -> list[Scope]:
    try:
        return traverse_scope(tree)
    except (OptimizeError, SqlglotError) as error:
        checks.add("PARSE_ERROR", f"cannot resolve query scopes: {error}"[:200])
        raise _Reject from None


def _count_protected(column: exp.Column) -> bool:
    """True when the column is the bare argument of COUNT(...) or COUNT(DISTINCT ...)."""
    parent = column.parent
    if isinstance(parent, exp.Distinct):
        parent = parent.parent
    return isinstance(parent, exp.Count)


class _Lineage:
    """Where each column reference comes from, and which outputs carry hidden PII."""

    def __init__(self, scopes: list[Scope], policy: Policy, dialect: str) -> None:
        self.policy = policy
        self.dialect = dialect
        self.by_expression = {id(s.expression): s for s in scopes}
        self.tables: set[str] = set()
        self.pii_refs: set[str] = set()
        self.forbidden: set[str] = set()
        self._memo: dict[tuple[int, int], bool] = {}
        seen: set[int] = set()
        for scope in scopes:
            for column in scope.columns:
                seen.add(id(column))
                source = self._source(scope, column)
                if isinstance(source, exp.Table):
                    self._real_ref(source.name.lower(), column)
            for node, source in scope.selected_sources.values():
                if isinstance(source, exp.Table):
                    self.tables.add(source.name.lower())
        # Backstop: a column no scope claimed is judged by name alone.
        root = scopes[-1].expression
        for column in root.find_all(exp.Column):
            if id(column) in seen or isinstance(column.this, exp.Star):
                continue
            for table in policy.models:
                if policy.is_pii(table, column.name):
                    self._real_ref(table, column)

    def _real_ref(self, table: str, column: exp.Column) -> None:
        name = column.name.lower()
        if not self.policy.is_pii(table, name):
            return
        ref = f"{table}.{name}"
        self.pii_refs.add(ref)
        if not _count_protected(column):
            self.forbidden.add(ref)

    @staticmethod
    def _source(scope: Scope, column: exp.Column):
        if not column.table:
            return None
        current = scope
        while current is not None:
            hit = current.sources.get(column.table)
            if hit is not None:
                return hit
            current = current.parent
        return None

    def hidden_outputs(self, scope: Scope) -> list[int]:
        return [i for i in range(len(_outputs(scope.expression))) if self._carries(scope, i)]

    def _carries(self, scope: Scope, index: int) -> bool:
        """Does output ``index`` of ``scope`` carry a hidden PII value?"""
        key = (id(scope), index)
        if key in self._memo:
            return self._memo[key]
        self._memo[key] = True  # cycle guard: assume the worst
        expression = scope.expression
        if isinstance(expression, exp.SetOperation):
            branches = [self.by_expression.get(id(b)) for b in (expression.left, expression.right)]
            result = any(b is None or self._carries(b, index) for b in branches)
        else:
            selects = _outputs(expression)
            result = index >= len(selects) or self._expression_carries(scope, selects[index])
        self._memo[key] = result
        return result

    def _expression_carries(self, scope: Scope, expression: exp.Expression) -> bool:
        for node in expression.walk():
            if isinstance(node, exp.Column):
                if _count_protected(node):
                    continue
                if self._column_carries(scope, node):
                    return True
            elif isinstance(node, (exp.Select, exp.SetOperation)) and node is not scope.expression:
                sub = self.by_expression.get(id(node))
                if sub is None or any(self._carries(sub, i) for i in range(len(_outputs(node)))):
                    return True
        return False

    def _column_carries(self, scope: Scope, column: exp.Column) -> bool:
        source = self._source(scope, column)
        if isinstance(source, exp.Table):
            return self.policy.is_hidden(source.name, column.name)
        if isinstance(source, Scope):
            names = [n.lower() for n in _output_names(source.expression, self.dialect)]
            name = column.name.lower()
            if name in names:
                return self._carries(source, names.index(name))
            return any(self._carries(source, i) for i in range(len(names)))
        # Unresolved: judge by name across the allowlist.
        return any(self.policy.is_hidden(t, column.name) for t in self.policy.models)


def _outputs(expression: exp.Expression) -> list[exp.Expression]:
    while isinstance(expression, exp.SetOperation):
        expression = expression.left
    if isinstance(expression, exp.Subquery):
        return _outputs(expression.this)
    return list(expression.selects) if isinstance(expression, exp.Select) else []


def _output_names(expression: exp.Expression, dialect: str) -> list[str]:
    return [s.alias_or_name or s.sql(dialect=dialect) for s in _outputs(expression)]


def _apply_limit(tree: exp.Expression, policy: Policy) -> exp.Expression:
    out = tree.copy()
    limit = out.args.get("limit")
    if limit is None and out.args.get("fetch") is None:
        return out.limit(policy.default_limit, copy=False)
    value = limit.expression if isinstance(limit, exp.Limit) else None
    if isinstance(value, exp.Literal) and not value.is_string and value.this.isdigit():
        if int(value.this) > policy.row_cap:
            limit.set("expression", exp.Literal.number(policy.row_cap))
        return out
    # Anything but a plain number (expression, percent, FETCH): cap from outside.
    return exp.select("*").from_(out.subquery("_q")).limit(policy.row_cap)


def _mask(query: exp.Expression, names: list[str], masked: list[int], policy: Policy) -> exp.Expression:
    """SELECT mask AS c1, c2 ... FROM (<query>): the inner query keeps its meaning."""
    inner = [f"_c{i}" for i in range(len(names))]
    alias = exp.TableAlias(
        this=exp.to_identifier("_q"),
        columns=[exp.to_identifier(c) for c in inner],
    )
    projections = []
    for i, name in enumerate(names):
        value = exp.Literal.string(policy.mask_value) if i in masked else exp.column(inner[i])
        projections.append(exp.alias_(value, name, quoted=True))
    return exp.select(*projections).from_(exp.Subquery(this=query, alias=alias))
