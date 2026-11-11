# governor-ask over MCP

`governor.ask.mcp_server` exposes governor-ask's read-only tools over MCP (stdio), so Claude Desktop, Cursor or any MCP client can search the catalog and run governed queries. It is a thin wrapper over `governor.ask.service`: no LLM calls, no writes, no natural-language-to-SQL.

Built on the official Python SDK, `mcp` 1.x (`FastMCP`). The repo pins `mcp<2` because 2.x renamed `FastMCP` and the tool fields.

## Run it

```bash
uv run python -m governor.ask.mcp_server
```

The process speaks MCP on stdin/stdout; errors go to stderr. It needs the built warehouse and metadata store (`artifacts/green/warehouse.duckdb`, `artifacts/meta.duckdb`), both opened read-only.

## Role

The role is fixed for the whole server process by the environment variable `GOVERNOR_MCP_ROLE` (default `analyst`). It must be a role defined in `knowledge/access.yaml`, or the server exits at start-up. No tool takes a role argument, so a client cannot raise its own permissions. To serve another role, start another server process with a different `GOVERNOR_MCP_ROLE`.

## Claude Desktop

Add this to `claude_desktop_config.json` (Settings, Developer, Edit config), replacing `<repo>` with the absolute path of this repository:

```json
{
  "mcpServers": {
    "governor-ask": {
      "command": "uv",
      "args": ["run", "--directory", "<repo>", "python", "-m", "governor.ask.mcp_server"],
      "env": { "GOVERNOR_MCP_ROLE": "analyst" }
    }
  }
}
```

Cursor takes the same `command`, `args` and `env` in `.cursor/mcp.json`.

## Tools

All tools are annotated read-only and return a JSON object.

| tool | arguments | result |
|---|---|---|
| `search_catalog` | `query: str`, `k: int = 5` (at most 20) | `{hits: [{card_id, kind, name, tables, score}]}`: BM25 over the catalog and metric cards |
| `describe_model` | `name: str` | `{name, description, owner, grain, columns: [{name, type, description, pii_tag}], tests}`; a model the role cannot query gives `{error}` |
| `get_lineage` | `name: str`, `direction: "upstream" \| "downstream" = "upstream"`, `depth: int = 2` (capped at 3) | `{name, direction, depth, nodes: [{unique_id, kind, name}]}` in topological order |
| `validate_sql` | `sql: str` | `{ok, codes, reasons, sql}`: the validator's verdict; `sql` is the rewritten query when ok |
| `run_governed_query` | `sql: str` | `{ok, codes, reasons, columns, rows, row_count}`: validated, dry-run, then run read-only with the role's limits |

`run_governed_query` always goes through the validator; a refused query returns `ok: false` with the validator's codes and no rows.

## Tests

```bash
uv run pytest -q tests/mcp
```

The tests start the server over stdio with the SDK client, list the tools and call each one.

# Certified KPIs over MCP (`governor-certified`)

`governor.ask.mcp_certified` is a second stdio server, beside `governor.ask.mcp_server` (which it does not change). It serves the certified KPI registry of the Postgres test bed: the MCP client chooses the KPI and the filters; the server builds the SQL in code, runs it through the validator (the allowlist is the certified models) and executes it read-only as the role's reader role. It makes no model call and takes no SQL.

## Run it

```bash
uv run python -m governor.ask.mcp_certified
```

It connects with the ask login, `GOVERNOR_PG_DSN`, on each tool call, so it starts and lists its tools without a database. Without one (or when the registry cannot be read) every tool returns `{"outcome": "error", "text": "<one line>"}`; the text never contains a connection string.

## Role

`GOVERNOR_MCP_ROLE` (default `analyst`) fixes the role for the process. It must be one of the certified reader roles (`analyst`, `finance_admin`), or the server exits at start-up with code 2. No tool takes a role argument; to serve the other role, start a second process.

## Claude Desktop / Cursor

```json
{
  "mcpServers": {
    "governor-certified": {
      "command": "uv",
      "args": ["run", "--directory", "<repo>", "python", "-m", "governor.ask.mcp_certified"],
      "env": { "GOVERNOR_MCP_ROLE": "analyst", "GOVERNOR_PG_DSN": "<the ask login DSN>" }
    }
  }
}
```

Put the DSN in the client's env (or the user environment), never in a file in this repo. Cursor takes the same block in `.cursor/mcp.json`.

## Tools

All read-only, each returns a JSON object.

| tool | arguments | result |
|---|---|---|
| `list_certified_kpis` | none | `{kpis: [{kpi_id, label, definition, grain, value_columns, owner, certified_by, certified_at}], not_available: [{kpi_id, missing, next_step}]}` |
| `describe_kpi` | `kpi_id: str` | `{outcome: "certified", ...the fields above, model, source_tier, source_ref, template_sha256}`; a gap gives `{outcome: "not_available", missing, typical_sources, next_step, text}`; anything else `{outcome: "unknown"}` |
| `query_kpi` | `kpi_id: str`, `value_column: str = null`, `period_kind: "month" \| "cohort" \| "year" \| "all" = "all"`, `period_value: str = null` (`YYYY-MM` or `YYYY`), `months_since_first: int = null`, `pick: "value" \| "max" \| "sum" = "value"` | `{outcome, text, value, kpi_id, sql, citation}`, outcome `answer`, `not_available` or `unanswerable` (the same path as `/v1/ask/certified`, after the model's choice); arguments that do not validate give `{outcome: "error", text}` and run no SQL |
| `gap_report` | none | `{gaps: [{kpi_id, missing, typical_sources, next_step}]}` |

Tests: `tests/mcp/test_mcp_certified.py` (in process with a fake adapter; stdio for the tool list and the no-database case).
