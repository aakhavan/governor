"""The MCP server over stdio, driven by the official SDK client. Offline: no LLM is used."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS = ["describe_model", "get_lineage", "run_governed_query", "search_catalog", "validate_sql"]


def _payload(result) -> dict:
    structured = result.structuredContent
    if isinstance(structured, dict):
        return structured.get("result", structured) if set(structured) == {"result"} else structured
    return json.loads(result.content[0].text)


def _session(calls: list[tuple[str, dict]], role: str | None = None) -> tuple[dict, list]:
    """Start the server, list its tools and make ``calls``; returns (input schemas by tool, payloads)."""
    env = {k: v for k, v in os.environ.items() if k != "GOVERNOR_MCP_ROLE"}
    if role:
        env["GOVERNOR_MCP_ROLE"] = role
    params = StdioServerParameters(command=sys.executable, args=["-m", "governor.ask.mcp_server"], env=env)

    async def run() -> tuple[dict, list]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                schemas = {t.name: t.inputSchema for t in tools}
                return schemas, [_payload(await session.call_tool(name, args)) for name, args in calls]

    return asyncio.run(run())


def test_lists_five_read_only_tools_without_a_role_argument():
    schemas, _ = _session([])
    assert sorted(schemas) == TOOLS
    assert all("role" not in (schema.get("properties") or {}) for schema in schemas.values())


def test_each_tool_once_as_the_default_role():
    _, (search, describe, unknown, lineage, valid, rows, pii, write) = _session(
        [
            ("search_catalog", {"query": "account open balance", "k": 2}),
            ("describe_model", {"name": "dim_accounts"}),
            ("describe_model", {"name": "stg_crm__accounts"}),
            ("get_lineage", {"name": "dim_accounts", "direction": "upstream", "depth": 50}),
            ("validate_sql", {"sql": "SELECT account_id FROM dim_accounts"}),
            ("run_governed_query", {"sql": "SELECT account_id, created_at FROM dim_accounts ORDER BY account_id LIMIT 3"}),
            ("run_governed_query", {"sql": "SELECT contact_email FROM dim_accounts"}),
            ("run_governed_query", {"sql": "DELETE FROM dim_accounts"}),
        ]
    )
    assert 1 <= len(search["hits"]) <= 2
    assert {"card_id", "kind", "name", "tables", "score"} <= set(search["hits"][0])

    assert describe["name"] == "dim_accounts" and describe["owner"]
    tags = {c["name"]: c["pii_tag"] for c in describe["columns"]}
    assert tags["contact_email"] and tags["account_id"] is None
    assert describe["tests"]
    assert "error" in unknown  # staging models are not queryable, so not described

    assert lineage["depth"] == 3 and lineage["direction"] == "upstream"
    assert any(n["kind"] == "source" for n in lineage["nodes"])

    assert valid["ok"] is True and "dim_accounts" in valid["sql"].lower()

    assert rows["ok"] is True and rows["row_count"] == 3
    assert rows["columns"] == ["account_id", "created_at"]
    assert all(isinstance(r[1], str) for r in rows["rows"])  # timestamps arrive as JSON strings

    assert pii["ok"] is False and "PII_FORBIDDEN" in pii["codes"]
    assert write["ok"] is False and write["row_count"] == 0


def test_role_comes_from_the_environment():
    _, (analyst,) = _session([("run_governed_query", {"sql": "SELECT contact_email FROM dim_accounts LIMIT 1"})])
    _, (admin,) = _session(
        [("run_governed_query", {"sql": "SELECT contact_email FROM dim_accounts LIMIT 1"})], role="finance_admin"
    )
    assert analyst["ok"] is False
    assert admin["ok"] is True and admin["row_count"] == 1


def test_unknown_role_refuses_to_start():
    env = {**os.environ, "GOVERNOR_MCP_ROLE": "superuser"}
    proc = subprocess.run(
        [sys.executable, "-m", "governor.ask.mcp_server"], env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL
    )
    assert proc.returncode == 2
    assert "GOVERNOR_MCP_ROLE" in proc.stderr
