# Demo script (5 minutes)

Shows governor-ask end to end: a metric answer, a clarification, a refusal, a masked answer, the trace explorer, the API with two role tokens, and MCP in Claude Desktop. The demo questions are written for the demo; they are not golden-set questions.

## Before the demo

```powershell
uv run python fixture/build_green.py
uv run python -m governor.core.harvest artifacts/green --out artifacts/meta.duckdb
uv run python -m governor.ask.catalog build

# two tokens, real models (OPENROUTER_API_KEY is already in the environment)
$env:GOVERNOR_API_TOKENS = "analyst:<analyst-token>,finance_admin:<admin-token>"
$env:GOVERNOR_LLM = "openrouter"
uv run uvicorn governor.api.app:app --port 8000          # terminal 1
uv run streamlit run apps/streamlit/app.py                # terminal 2, opens localhost:8501
```

Do a dry run of each question once beforehand: model output varies between runs. Have `README.md` (Evaluation) open in a tab.

## 0:00 to 0:30: the problem

"Text-to-SQL bots answer fast but guess on ambiguous questions and will select a customer's email for anyone. governor-ask lets the model plan and draft; Python owns the policy, the validator, the execution and every number." Show the graph diagram in the README.

## 0:30 to 1:15: a metric question (Ask page, analyst token)

Paste the analyst token, open **Ask**:

> What was our MRR at the end of last month?

Point out: the answer's number comes from the result rows, not the model; the SQL, the models it read (lineage) and the data freshness (as_of 2026-10-22) are shown under the answer. "Last month" was resolved against the pinned as_of, not today's date.

## 1:15 to 1:55: an ambiguous question (clarify)

> How are our customers doing?

The agent asks which measure is meant instead of guessing. Answer it (for example "MRR by plan") and show that the thread resumes and answers. A clarified question gets its trace only once it is answered.

## 1:55 to 2:30: an analyst PII refusal

> List the email addresses of our ten largest customers.

Refused, and the refusal names the rule (PII for the analyst role only inside a count). Then:

> How many distinct contact emails do we have?

Answered: a count of a PII column is a number. Neither prompt restates the policy; it lives in `knowledge/access.yaml`.

## 2:30 to 3:00: a finance_admin masked answer

Switch to the finance_admin token:

> Show the contact names of our five largest customers by MRR.

The rows come back with the contact names as `***`. Masking is an outer projection inside DuckDB, so the raw names never leave the database. (The contact email is granted to finance_admin in access.yaml, so it would be shown; the name is not.)

## 3:00 to 3:40: the trace explorer

Open **Trace explorer**: one row per question with role, outcome, the plan, every SQL attempt with its validator codes, the executed SQL, cost and latency. The question is stored as a hash, and PII cells are masked in the trace. Open the refused trace and show the policy decision. Switch back to the analyst token: finance_admin's traces are not visible.

## 3:40 to 4:20: the API with two tokens (curl)

```bash
curl -s localhost:8000/health

curl -s -X POST localhost:8000/v1/ask -H "Authorization: Bearer <analyst-token>" \
     -H "Content-Type: application/json" -d '{"question": "Show the contact names of our five largest customers by MRR"}'
# -> status "refused"

curl -s -X POST localhost:8000/v1/ask -H "Authorization: Bearer <admin-token>" \
     -H "Content-Type: application/json" -d '{"question": "Show the contact names of our five largest customers by MRR"}'
# -> status "answered", contact names "***"

curl -s -X POST localhost:8000/v1/ask -H "Authorization: Bearer <analyst-token>" \
     -H "Content-Type: application/json" -d '{"question": "how many accounts", "role": "finance_admin"}'
# -> 422: the role comes only from the token
```

## 4:20 to 4:50: MCP in Claude Desktop

With the `governor-ask` server configured (`docs/mcp.md`, `GOVERNOR_MCP_ROLE=analyst`), ask Claude Desktop: "Use governor-ask to find the model with invoices and describe it, then count invoices by status." Show the tool calls (`search_catalog`, `describe_model`, `run_governed_query`). Then ask it to select contact emails: `run_governed_query` returns `ok: false` with the validator's code. Same policy, different client.

## 4:50 to 5:00: honest numbers

Holdout, run once after the prompts were frozen: execution accuracy 0.700 for the agent vs 0.600 for the baseline, policy compliance 1.000 vs 0.333, no PII leak vs a leak. The agent loses on join and time_grain items, at about 2.8x the cost and 3x the latency, on a small four-mart catalog. Details in `evaluation/eval_report.md`.
