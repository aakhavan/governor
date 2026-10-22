"""G9 acceptance (stretch step): MCP stdio server with exactly 5 read-only tools, role fixed by env, via the official SDK client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, last_json, pytest_check, run, tail  # noqa: E402

TOOLS = ["describe_model", "get_lineage", "run_governed_query", "search_catalog", "validate_sql"]

CLIENT = r'''
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def payload(res):
    sc = getattr(res, "structuredContent", None)
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    for c in getattr(res, "content", []) or []:
        t = getattr(c, "text", None)
        if t:
            try:
                return json.loads(t)
            except json.JSONDecodeError:
                return {"text": t}
    return {}

async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "governor.ask.mcp_server"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            out = {"tools": tools}
            out["search"] = payload(await s.call_tool("search_catalog", {"query": "monthly recurring revenue", "k": 3}))
            out["describe"] = payload(await s.call_tool("describe_model", {"name": "dim_accounts"}))
            out["describe_bad"] = payload(await s.call_tool("describe_model", {"name": "no_such_model"}))
            out["lineage"] = payload(await s.call_tool("get_lineage", {"name": "mrr_monthly", "direction": "upstream", "depth": 9}))
            out["validate_bad"] = payload(await s.call_tool("validate_sql", {"sql": "DROP TABLE dim_accounts"}))
            out["query_ok"] = payload(await s.call_tool("run_governed_query", {"sql": "SELECT country, count(*) AS n FROM dim_accounts GROUP BY country"}))
            out["query_pii"] = payload(await s.call_tool("run_governed_query", {"sql": "SELECT contact_email FROM dim_accounts"}))
            schemas = {t.name: sorted((t.inputSchema or {}).get("properties", {})) for t in (await s.list_tools()).tools}
            out["role_args"] = [n for n, props in schemas.items() if "role" in props]
            out["query_write"] = payload(await s.call_tool("run_governed_query", {"sql": "DELETE FROM fct_invoices"}))
    print(json.dumps(out, default=str))

asyncio.run(main())
'''


def mcp_client():
    r = run([sys.executable, "-c", CLIENT], timeout=180)
    d = last_json(r.stdout)
    if not check("MCP server answers the SDK stdio client", d is not None, tail(r)):
        return
    check("exactly the 5 specified tools", d["tools"] == TOOLS, d["tools"])
    tabs = {t for h in d["search"].get("hits", []) for t in h.get("tables", [])}
    check("search_catalog finds mrr_monthly", "mrr_monthly" in tabs, str(d["search"])[:200])
    cols = {c.get("name"): c.get("pii_tag") for c in d["describe"].get("columns", [])}
    check("describe_model shows PII tags", bool(cols.get("contact_email")) and bool(cols.get("contact_name")), str(cols)[:200])
    check("describe_model on an unknown name returns an error, not a crash", "error" in d["describe_bad"], str(d["describe_bad"])[:120])
    check("get_lineage returns upstream nodes (depth capped)", bool(d["lineage"].get("nodes")), str(d["lineage"])[:160])
    check("validate_sql rejects DROP", d["validate_bad"].get("ok") is False, str(d["validate_bad"])[:160])
    q = d["query_ok"]
    check("run_governed_query returns rows for a valid query", q.get("ok") is True and q.get("row_count", 0) > 0, str(q)[:160])
    check("run_governed_query refuses analyst PII by default", d["query_pii"].get("ok") is False
          and "PII_FORBIDDEN" in d["query_pii"].get("codes", []), str(d["query_pii"])[:160])
    check("run_governed_query cannot write", d["query_write"].get("ok") is False, str(d["query_write"])[:160])
    check("no tool takes a role argument (role is fixed by GOVERNOR_MCP_ROLE)", not d["role_args"], str(d["role_args"]))


def docs():
    p = ROOT / "docs/mcp.md"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    check("docs/mcp.md has the run command and all tool names", "governor.ask.mcp_server" in text
          and all(t in text for t in TOOLS), "")


guarded("mcp", mcp_client)
guarded("docs", docs)
pytest_check("tests/mcp")
finish("G9")
