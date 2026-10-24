# G5b walkthrough: the executor

*Gate review, 23 Oct 2026. Drafted by Claude from the step's output; read, edited and approved by Amir.*

**What it is.** The only place where SQL touches the warehouse: `execute(sql, role)` in `src/governor/ask/executor.py`. Nothing in the agent, the API or the MCP server runs SQL any other way.

**The order matters.** 1) `validate()` checks the SQL for this role (G5a) and returns a *rewritten* query: masks applied, LIMIT added or lowered. 2) `dry_run()` plans that rewritten query with `EXPLAIN`, so a broken query fails before it runs. 3) `run_readonly()` runs it with the role's timeout and row cap. The user's original SQL never runs; a rejected query returns codes and reasons, never rows.

**The connection is locked down.** Read-only DuckDB; external access, extension autoload and community extensions off; then `lock_configuration`, so a query can't switch them back on. So `read_csv('C:/…')`, `COPY … TO` or `ATTACH` fail even if the validator missed them: two layers, like the regex guard plus the model flag in Sprint 3.

**Limits come from data.** Timeout (10 s), row cap (1000) and default LIMIT (100) are read from `knowledge/access.yaml`, not hard-coded. A timeout is reported as `TIMEOUT`, other failures as `EXEC_ERROR`.

**Reviews.** Grok and Fable both passed it with no fixes. Fable's note: the `EXPLAIN` dry run is not on the timeout timer. Planning an already-validated SELECT is fast, so it is low risk, but a hardened version would time it too.

**What I would defend in an interview.** Why the executor re-validates even though the graph already did (defence in depth, and the MCP server calls it directly); why the rewritten SQL runs, not the user's; why policy is data.
