"""The certified-KPI MCP server (batch2d section 23): in process with a fake adapter, and over stdio without a database."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from governor.ask import mcp_certified as m

TOOLS = ["describe_kpi", "gap_report", "list_certified_kpis", "query_kpi"]
MARKER = "postgresql://governor_ask:s3cret-marker@db.example:5432/governor"
AT = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)
CERTIFIED = [
    ("cohort_retention", "kpi_cohort_retention", "Monthly cohort retention", "Share retained.", "cohort_month",
     ["retention"], "Owner A", "platform", "https://example.test/ret", "certifier", AT, "c0ffee"),
    ("gmv", "kpi_gmv", "Gross merchandise value", "Item price plus freight.", "month", ["gmv"], "Owner A",
     "platform", "https://example.test/gmv", "certifier", AT, "c0ffee"),
]
GAPS = [("conversion_rate", ["sessions"], ["web analytics"], "Load session data from the web analytics tool.")]
COLUMNS = {
    "kpi_gmv": [("month", "timestamp without time zone"), ("gmv", "numeric")],
    "kpi_cohort_retention": [("cohort_month", "timestamp without time zone"), ("months_since_first", "numeric"),
                             ("retention", "numeric")],
}


class FakeAdapter:
    """Registry reads from the fixtures above; KPI queries answer from ``results``; ``fail`` raises like no database."""

    def __init__(self, results=None, fail: str | None = None):
        self.results = list(results or [])
        self.fail = fail
        self.calls: list[tuple[str, str | None]] = []

    def run(self, sql_text, *, timeout_s, row_cap, native=False, role=None):
        from governor.core.adapters.base import QueryError

        self.calls.append((sql_text, role))
        if self.fail:
            raise QueryError(self.fail)
        if "template_sha256" in sql_text:
            return ["template_sha256"], [["t-hash-1"]]
        if "governor_certified" in sql_text and "information_schema" not in sql_text:
            return ["kpi_id"], [list(r) for r in CERTIFIED]
        if "governor_gaps" in sql_text:
            return ["kpi_id"], [list(r) for r in GAPS]
        if "information_schema.columns" in sql_text:
            return ["t", "c", "d"], [[t, col, typ] for t, cols in COLUMNS.items() for col, typ in cols]
        return ["grain_value", "kpi_value"], self.results.pop(0) if self.results else []

    def kpi_queries(self):
        return [s for s, _ in self.calls if "information_schema" not in s and "governor_" not in s]


def _payload(result) -> dict:
    """A tool result as a dict, from FastMCP.call_tool (in process) or ClientSession.call_tool (stdio)."""
    if isinstance(result, tuple):
        result = result[1] if isinstance(result[1], dict) else result[0]
    if isinstance(result, dict):
        return result.get("result", result) if set(result) == {"result"} else result
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured.get("result", structured) if set(structured) == {"result"} else structured
    content = result.content if hasattr(result, "content") else result
    return json.loads(content[0].text)


def call(adapter, name, args=None, role="analyst") -> dict:
    server = m.build_server(role, adapter=adapter)
    return _payload(asyncio.run(server.call_tool(name, args or {})))


def _stdio(calls, env_extra=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GOVERNOR_MCP_ROLE", "GOVERNOR_PG_DSN", "GOVERNOR_PG_ADMIN_DSN")}
    env.update(env_extra or {})
    params = StdioServerParameters(command=sys.executable, args=["-m", "governor.ask.mcp_certified"], env=env)

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                return tools, [_payload(await session.call_tool(n, a)) for n, a in calls]

    return asyncio.run(run())


def test_lists_four_read_only_tools_without_a_role_argument():
    tools, _ = _stdio([])
    assert sorted(t.name for t in tools) == TOOLS
    for tool in tools:
        props = tool.inputSchema.get("properties") or {}
        assert "role" not in props and "sql" not in props
        assert tool.annotations.readOnlyHint is True and tool.annotations.destructiveHint is False


def test_list_certified_kpis_and_gaps():
    adapter = FakeAdapter()
    out = call(adapter, "list_certified_kpis")
    assert [k["kpi_id"] for k in out["kpis"]] == ["cohort_retention", "gmv"]
    gmv = out["kpis"][1]
    assert set(gmv) == {"kpi_id", "label", "definition", "grain", "value_columns", "owner", "certified_by",
                        "certified_at"}
    assert gmv["value_columns"] == ["gmv"] and gmv["certified_at"].startswith("2026-11-05")
    assert out["not_available"] == [{"kpi_id": "conversion_rate", "missing": ["sessions"],
                                     "next_step": "Load session data from the web analytics tool."}]
    assert all(role == "governor_analyst" for _, role in adapter.calls) and not adapter.kpi_queries()


def test_describe_kpi_certified_gap_and_unknown():
    adapter = FakeAdapter()
    gmv = call(adapter, "describe_kpi", {"kpi_id": "gmv"})
    assert gmv["outcome"] == "certified" and gmv["model"] == "kpi_gmv" and gmv["grain"] == "month"
    assert gmv["source_tier"] == "platform" and gmv["source_ref"] == "https://example.test/gmv"
    assert gmv["template_sha256"] == "t-hash-1"
    gap = call(adapter, "describe_kpi", {"kpi_id": "conversion_rate"})
    assert gap["outcome"] == "not_available" and gap["missing"] == ["sessions"]
    assert gap["typical_sources"] == ["web analytics"] and "Load session data" in gap["next_step"]
    assert call(adapter, "describe_kpi", {"kpi_id": "no_such_kpi"})["outcome"] == "unknown"
    assert not adapter.kpi_queries()
    # In the KPI catalogue but neither certified nor a registry gap: still unknown, no KPI query.
    catalogued = call(adapter, "describe_kpi", {"kpi_id": "gross_margin"})
    assert catalogued == {"outcome": "unknown", "kpi_id": "gross_margin"}
    assert not adapter.kpi_queries()


def test_query_kpi_runs_validated_sql_as_the_reader_role():
    adapter = FakeAdapter([[[dt.datetime(2026, 1, 1), Decimal("455.0")]]])
    out = call(adapter, "query_kpi", {"kpi_id": "gmv", "period_kind": "month", "period_value": "2026-01"},
               role="finance_admin")
    assert out["outcome"] == "answer" and out["value"] == 455.0 and out["kpi_id"] == "gmv"
    assert "455" in out["text"] and out["citation"]["kpi_id"] == "gmv"
    assert '"serve_finance_admin"."kpi_gmv"' in out["sql"]
    assert adapter.kpi_queries() == [out["sql"]]
    assert all(role == "governor_finance_admin" for _, role in adapter.calls)


def test_query_kpi_gap_is_not_available():
    adapter = FakeAdapter()
    out = call(adapter, "query_kpi", {"kpi_id": "conversion_rate"})
    assert out["outcome"] == "not_available" and "sessions" in out["text"] and not out["sql"]
    assert not adapter.kpi_queries()


@pytest.mark.parametrize("args", [
    {"kpi_id": "gmv", "period_kind": "week", "period_value": "2026-01"},
    {"kpi_id": "gmv", "pick": "median"},
    {"kpi_id": "cohort_retention", "period_kind": "cohort", "period_value": "2026-01", "months_since_first": -1},
])
def test_query_kpi_bad_arguments_run_no_sql(args):
    adapter = FakeAdapter()
    out = call(adapter, "query_kpi", args)
    assert out["outcome"] == "error" and "\n" not in out["text"]
    assert adapter.calls == []
    # an expressible-looking but invalid value reaches the builder, never the database
    adapter = FakeAdapter()
    out = call(adapter, "query_kpi", {"kpi_id": "gmv", "period_kind": "month", "period_value": "2026-01'; DROP x"})
    assert out["outcome"] == "unanswerable" and not adapter.kpi_queries()


def test_gap_report_lists_missing_data_and_next_step():
    out = call(FakeAdapter(), "gap_report")
    assert out == {"gaps": [{"kpi_id": "conversion_rate", "missing": ["sessions"], "typical_sources": ["web analytics"],
                             "next_step": "Load session data from the web analytics tool."}]}


def test_no_database_is_a_clean_error():
    tools, outs = _stdio([("list_certified_kpis", {}), ("describe_kpi", {"kpi_id": "gmv"}),
                          ("query_kpi", {"kpi_id": "gmv"}), ("gap_report", {})])
    assert len(tools) == 4
    for out in outs:
        assert out["outcome"] == "error" and out["text"] and "\n" not in out["text"]
    # a driver message that carries a connection string never reaches the client
    out = call(FakeAdapter(fail=f"could not connect to {MARKER} password=s3cret-marker"), "list_certified_kpis")
    assert out["outcome"] == "error" and "s3cret-marker" not in out["text"] and "db.example" not in out["text"]


def test_role_must_be_a_reader_role(monkeypatch):
    for role in ("superuser", "governor_analyst", ""):
        with pytest.raises(ValueError):
            m.build_server(role, adapter=FakeAdapter())
    monkeypatch.setenv("GOVERNOR_MCP_ROLE", "governor_finance_admin")
    with pytest.raises(SystemExit):
        m.server_role()
    monkeypatch.delenv("GOVERNOR_MCP_ROLE")
    assert m.server_role() == "analyst"
    env = {**os.environ, "GOVERNOR_MCP_ROLE": "superuser"}
    proc = subprocess.run([sys.executable, "-m", "governor.ask.mcp_certified"], env=env, capture_output=True,
                          text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert proc.returncode == 2 and "GOVERNOR_MCP_ROLE" in proc.stderr
