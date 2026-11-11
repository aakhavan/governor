"""Certified KPIs over MCP (stdio): the second server, ``governor-certified`` (docs/capstone/batch2d.md section 23).

Four read-only tools over the certified KPI registry. No model call: the MCP client chooses the KPI and the
filters, code builds and validates the SQL (``certified.answer_reply``) and runs it as the role's reader role.
No tool takes SQL or a role. The role is fixed for the process by ``GOVERNOR_MCP_ROLE`` (default ``analyst``)
and must be one of ``certified.READER_ROLES``.

    uv run python -m governor.ask.mcp_certified

Every failure (no database, unreadable registry, bad arguments) is returned as
``{"outcome": "error", "text": <one line>}``; the text never carries a connection string.
Built on the official ``mcp`` SDK 1.x (``FastMCP``). Stdout carries the protocol; errors go to stderr.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Callable

import pydantic
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from governor.ask import certified as c

DEFAULT_ROLE = "analyst"
SERVER_NAME = "governor-certified"
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_KEYVAL = re.compile(r"\b(password|user|host|hostaddr|dbname|port|dsn|sslmode)\s*=\s*\S+", re.IGNORECASE)
_MAX_TEXT = 300


def server_role() -> str:
    """The role this process serves, from ``GOVERNOR_MCP_ROLE``; it must be a certified reader role."""
    role = os.environ.get("GOVERNOR_MCP_ROLE", "").strip() or DEFAULT_ROLE
    if role not in c.READER_ROLES:
        raise SystemExit(f"GOVERNOR_MCP_ROLE={role!r} is not a certified reader role; expected one of "
                         f"{sorted(c.READER_ROLES)}")
    return role


def safe_text(message: Any) -> str:
    """One line, no connection string, at most 300 characters."""
    text = " ".join(str(message).split())
    text = _KEYVAL.sub(lambda m: f"{m.group(1)}=***", _URL.sub("<connection>", text))
    return text[:_MAX_TEXT] or "unknown error"


def _error(message: Any) -> dict:
    return {"outcome": "error", "text": safe_text(message)}


def _guard(fn: Callable[[], dict]) -> dict:
    try:
        return fn()
    except pydantic.ValidationError as error:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}"
                             for e in error.errors())
        return _error(f"invalid arguments: {problems}")
    except c.CertifiedError as error:
        return _error(error)
    except Exception as error:  # noqa: BLE001 - a tool never crashes the server
        return _error(f"certified KPIs are not available: {type(error).__name__}: {error}")


def _when(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _kpi_fields(kpi: c.CertifiedKpi) -> dict:
    return {
        "kpi_id": kpi.kpi_id, "label": kpi.label, "definition": kpi.definition, "grain": kpi.grain,
        "value_columns": list(kpi.value_columns), "owner": kpi.owner, "certified_by": kpi.certified_by,
        "certified_at": _when(kpi.certified_at),
    }


def _gap_fields(gap: c.Gap) -> dict:
    return {"kpi_id": gap.kpi_id, "missing": list(gap.missing), "typical_sources": list(gap.typical_sources),
            "next_step": gap.next_step}


def _template_hash(adapter: Any, registry: c.Registry, kpi_id: str) -> str | None:
    """The certified template hash, when the registry has the column; None otherwise."""
    literal = "'" + kpi_id.replace("'", "''") + "'"
    try:
        _, rows = adapter.run(f"SELECT template_sha256 FROM {registry.schema}.{c.REGISTRY} WHERE kpi_id = {literal}",
                              timeout_s=10, row_cap=1, native=True, role=c.reader_role(registry.role))
    except Exception:  # noqa: BLE001 - optional field
        return None
    return str(rows[0][0]) if rows and rows[0] and rows[0][0] else None


def build_server(role: str, adapter: Any = None) -> FastMCP:
    """An MCP server whose tools all read the certified registry as ``role``'s reader role.

    ``adapter`` defaults to the ask login (``GOVERNOR_PG_DSN``), made per call, so the server starts without a database.
    """
    c.reader_role(role)  # ValueError for anything but a certified reader role

    def connect() -> Any:
        return adapter if adapter is not None else c.default_adapter()

    mcp = FastMCP(
        name=SERVER_NAME,
        instructions=(
            "Read-only certified KPIs: list them, describe one, query one by id with a period and pick, and see "
            "which KPIs are not available and why. You choose the KPI and filters; the server builds and validates "
            "the SQL. The role is fixed by the server."
        ),
    )

    @mcp.tool(annotations=READ_ONLY)
    def list_certified_kpis() -> dict:
        """The certified KPIs this role can query (id, label, definition, grain, value columns, owner, who certified
        it and when) and the KPIs that are not available, with the missing data and the next step."""

        def run() -> dict:
            registry = c.read_registry(connect(), role)
            return {
                "kpis": [_kpi_fields(k) for k in registry.kpis.values()],
                "not_available": [{"kpi_id": g.kpi_id, "missing": list(g.missing), "next_step": g.next_step}
                                  for g in registry.gaps.values()],
            }

        return _guard(run)

    @mcp.tool(annotations=READ_ONLY)
    def describe_kpi(kpi_id: str) -> dict:
        """One KPI: outcome certified with its fields, gold model, source tier and reference and template hash;
        not_available with the missing data, typical sources and next step; or unknown."""

        def run() -> dict:
            db = connect()
            registry = c.read_registry(db, role)
            kpi = registry.kpis.get(kpi_id)
            if kpi is not None:
                out = {"outcome": "certified", **_kpi_fields(kpi), "model": kpi.model,
                       "source_tier": kpi.source_tier, "source_ref": kpi.source_ref}
                template = _template_hash(db, registry, kpi_id)
                if template:
                    out["template_sha256"] = template
                return out
            gap = registry.gaps.get(kpi_id)
            if gap is not None:
                return {"outcome": "not_available", **_gap_fields(gap), "text": c._gap_text(kpi_id, gap)}
            return {"outcome": "unknown", "kpi_id": kpi_id}

        return _guard(run)

    @mcp.tool(annotations=READ_ONLY)
    def query_kpi(
        kpi_id: str,
        value_column: str | None = None,
        period_kind: str = "all",
        period_value: str | None = None,
        months_since_first: int | None = None,
        pick: str = "value",
    ) -> dict:
        """The value of one certified KPI. period_kind: month (period_value YYYY-MM), cohort (YYYY-MM), year (YYYY)
        or all. pick: value, max or sum. months_since_first only for KPIs with that column. Returns outcome
        (answer, not_available, unanswerable or error), text, value, kpi_id, sql and citation."""

        def run() -> dict:
            reply = c.CertifiedReply(
                kpi_id=kpi_id, value_column=value_column,
                period=c.Period(kind=period_kind, value=period_value),
                months_since_first=months_since_first, pick=pick, category="answer")
            return c.answer_reply(reply, role, connect()).model_dump(mode="json")

        return _guard(run)

    @mcp.tool(annotations=READ_ONLY)
    def gap_report() -> dict:
        """Every KPI that is not available: the missing data, typical sources and the next step."""

        def run() -> dict:
            registry = c.read_registry(connect(), role)
            return {"gaps": [_gap_fields(g) for g in registry.gaps.values()]}

        return _guard(run)

    return mcp


def main() -> int:
    try:
        role = server_role()
    except SystemExit as error:
        print(error, file=sys.stderr)
        return 2
    build_server(role).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
