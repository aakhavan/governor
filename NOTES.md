# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G9 is an MCP stdio server on mcp 1.30.0 (FastMCP, pin mcp>=1.10,<2). python -m governor.ask.mcp_server exposes search_catalog, describe_model, get_lineage, validate_sql, and run_governed_query as a thin wrapper over governor.ask.service. The process role comes only from GOVERNOR_MCP_ROLE (default analyst; an unknown role exits 2). SQL goes through validator.validate and executor.execute on a read-only warehouse connection. describe_model and get_lineage open meta.duckdb read-only and only for models that role's Policy allows; lineage depth is capped at 3. Search is offline BM25. The Streamlit client is unchanged. as_of remains 2026-10-22.

## Open questions
- G2b gate review (claude.ai, 22 Oct): golden set fine; but `fixture/build_green.py` stamps as_of from the wall clock (Sprint 4 behaviour), so a rebuild on another day shifts days_outstanding/overdue answers and breaks the golden as_of check. Spec change for G3 (item 0 + locked check): pin as_of in `fixture/AS_OF` = 2026-10-22T14:11:26+00:00. Needs `factory relock` before `approve G2b`.
- `fct_invoices.days_outstanding` follows the spec literally: 0 only when fully paid. Void invoices (416 not paid) therefore show days outstanding. Should void count as 0 / be excluded? (Amir decides; one-line change in the SQL.)
- `as_of` is the build's wall-clock instant (S4 design: source freshness needs `_loaded_at` within 12 h). Data dates are fixed (seed 42) but `days_outstanding` shifts with each rebuild. Pin as_of if golden answers must be stable across rebuilds.
- `governor.core.config` replaces S4 `triage.config`, which was not imported. Values reconstructed: `ALLOWED_MODELS` from the S4 test, MAX_TOKENS 4096 from the llm docstring; `FAST_MODEL` (`openai/gpt-5-nano`) and `EMBED_MODEL` (`openai/text-embedding-3-small`) are guesses, overridable by env. Check before G4/G5 use them.
- `chromadb` is not a dependency (not in the G1 list). `retrieval.build_index/load_index` need it; add it in the step that uses dense retrieval.
- access.yaml: every model and grant name matches the real warehouse (allowlist = the four marts; `dim_accounts.contact_email` exists and is tagged `email`). No renames needed.
- Capstone brief not yet available; PLAN §1 holds the provisional stance (ask = spine, one triage path = stretch).
- G2b gold numbers are frozen against as_of 2026-10-22T14:11:26+00:00 and the current green build. m05, m06 and j04 depend on days_outstanding / paid amounts; a rebuild that moves as_of changes them and the gold must be rechecked (FROZEN hashes cover the files, not the results).
- G2b metric gold (m01-m03) mirrors metrics.yaml and returns (month_start, value). compare needs equal column counts, so a bare number fails these items. Amir: keep (forces the snapshot month to be stated), or drop month_start from the gold?
- Sol suggested comparing column names/types in the checker; kept name-agnostic on purpose (LLM aliases vary; Spider-style execution accuracy), with equal column counts and permutation matching.

- G3: dbt `source freshness` measures `_loaded_at` against the wall clock (DuckDB now()), and `_loaded_at` is now the pinned as_of, so green sources report warn after 12 h and error after 24 h. build_green.py accepts that (status pass/warn/error, 2 results) instead of failing. Side effect: green sources.json / meta.freshness are not "pass", so `lineage.failing_nodes` on the green build would flag the two sources. Clean fix (outside G3 paths): a project macro overriding `collect_freshness` to use `var('as_of')` as snapshotted_at, or `loaded_at_query` in _sources.yml. Amir decides.
- G3: the prompt gave AS_OF as `2026-10-22T14:11:26+00:00`, but the locked check compares against `str()` of the YAML datetime, so fixture/AS_OF and as_of.txt use `2026-10-22 14:11:26+00:00` (same instant; fromisoformat reads both).
- G3: `--llm` defaults to `fake` so nothing spends money by accident; G10 must pass `--llm openrouter`. The report records `llm`.

## G9 result (implementer notes)
- `src/governor/ask/mcp_server.py` (`python -m governor.ask.mcp_server`, stdio): 5 read-only tools (`search_catalog`, `describe_model`, `get_lineage`, `validate_sql`, `run_governed_query`), all annotated readOnlyHint. Role from `GOVERNOR_MCP_ROLE` (default analyst), checked against access.yaml at start-up (exit 2 otherwise); no tool has a role argument.
- Logic in `governor.ask.service`: `search_catalog` (BM25, offline; k capped at 20), `describe_model`/`get_lineage` (from meta.duckdb, only models the role's policy can query; staging models give `{error}`), `validate_sql` (validator), `run_query` (executor.execute; rows made JSON-safe with pydantic_core). Lineage depth capped at 3; result includes the applied `depth`.
- SDK: **mcp 1.30.0**, pinned `mcp>=1.10,<2`. 2.3.0 was installed first: it renames `FastMCP` to `MCPServer` and `Tool.inputSchema` to `input_schema`, and the locked accept_g9 client reads `inputSchema`, so 2.x fails acceptance. Revisit the pin when the plan moves to 2.x.
- `describe_model` reuses `catalog._grain` (private helper) so the grain matches the cards.
- `StdioServerParameters` without `env` passes only a minimal environment, so `GOVERNOR_MCP_ROLE` must go in the client's `env` (docs/mcp.md shows it).
- Open: dates in rows arrive as ISO strings, Decimals as strings (pydantic default).
Tests: `tests/mcp/test_mcp_server.py` (4, real stdio server + SDK client).

## G9 result
*MCP server with 5 read-only tools (stretch: cut first if late), 23 Oct 2026 19:58.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G9`.

| check | ok | detail |
|---|---|---|
| MCP server answers the SDK stdio client | yes | Processing request of type CallToolRequest | Processing request of type ListToolsRequest | Processing request of type Ca |
| exactly the 5 specified tools | yes | ['describe_model', 'get_lineage', 'run_governed_query', 'search_catalog', 'validate_sql'] |
| search_catalog finds mrr_monthly | yes | {'hits': [{'card_id': 'metric:arr', 'kind': 'metric', 'name': 'arr', 'tables': ['mrr_monthly'], 'score': 3.449297}, {'ca |
| describe_model shows PII tags | yes | {'account_id': None, 'company_name': None, 'contact_email': 'email', 'contact_name': 'name', 'country': None, 'created_a |
| describe_model on an unknown name returns an error, not a crash | yes | {'error': "unknown model 'no_such_model'"} |
| get_lineage returns upstream nodes (depth capped) | yes | {'name': 'mrr_monthly', 'direction': 'upstream', 'depth': 3, 'nodes': [{'unique_id': 'source.billing_mart.billing.plans' |
| validate_sql rejects DROP | yes | {'ok': False, 'codes': ['NOT_SELECT'], 'reasons': ['Drop statement; only SELECT or WITH ... SELECT is allowed'], 'sql':  |
| run_governed_query returns rows for a valid query | yes | {'ok': True, 'codes': [], 'reasons': [], 'columns': ['country', 'n'], 'rows': [['Aserbaidschan', 5], ['Südgeorgien und d |
| run_governed_query refuses analyst PII by default | yes | {'ok': False, 'codes': ['PII_FORBIDDEN'], 'reasons': ["PII column dim_accounts.contact_email used outside COUNT(...) for |
| run_governed_query cannot write | yes | {'ok': False, 'codes': ['NOT_SELECT'], 'reasons': ['Delete statement; only SELECT or WITH ... SELECT is allowed'], 'colu |
| no tool takes a role argument (role is fixed by GOVERNOR_MCP_ROLE) | yes | [] |
| docs/mcp.md has the run command and all tool names | yes |  |
| pytest tests/mcp | yes | 4 passed in 16.87s |

Review: G9 matches the prompt. FastMCP stdio server exposes the five read-only tools as a wrapper over governor.ask.service. Role comes only from GOVERNOR_MCP_ROLE. validate_sql and run_governed_query call validator.validate and executor.execute (read-only warehouse). describe_model and get_lineage use Policy.for_role and a read-only meta store; lineage depth caps at 3. Descriptions do not restate access.yaml. Live SDK output matches the warehouse and validator codes.

For Amir: accept_g9's write check only requires ok false. Writes still cannot land: run_governed_query calls executor.execute, which validates and opens the warehouse read-only. The lineage check only requires a non-empty node list; the recorded payload has depth 3 after a request for 9, and tests/mcp asserts the cap when depth is 50. Models outside the allowlist use the same error shape as a missing name. mcp stays below 2 because accept_g9 reads Tool.inputSchema.

## Additions for G10a
G10a tunes ask prompts. The MCP server is not on the graph path: do not import mcp_server into the graph and do not add an NL-to-SQL tool. Role stays out of tool arguments and request bodies. mcp is pinned to >=1.10,<2 (installed 1.30.0); 2.x renames FastMCP and Tool.inputSchema, which the locked accept_g9 client reads. service now has search_catalog (BM25, k capped at 20), describe_model, get_lineage (depth capped at 3), validate_sql, and run_query. Query rows are JSON-safe (dates and decimals as strings). Tool text must not restate access.yaml. as_of remains 2026-10-22. Do not read evaluation/golden. No holdout run in G10a.
