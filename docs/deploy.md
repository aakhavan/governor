# Deploying governor-ask

This is a **single-tenant portfolio deployment**: one container, one fixed
warehouse built into the image, a handful of role tokens shared by people you
trust. It is not a multi-tenant service. There are no user accounts or token
rotation endpoints, and there is no rate limiting beyond the query limits in
`knowledge/access.yaml`.

## What runs

One FastAPI app, `governor.api.app:app` (uvicorn, port 8000):

| route | auth | what |
|---|---|---|
| `GET /health` | none | `{status, as_of, version}` |
| `POST /v1/ask` | bearer | body `{question, thread_id?}` -> AskResult |
| `POST /v1/threads/{thread_id}/resume` | bearer | body `{answer}` -> AskResult |
| `GET /v1/traces?outcome=&limit=` | bearer | the caller's decision traces, newest first |
| `GET /v1/traces/{trace_id}` | bearer | one of the caller's traces |

AskResult: `status` (answered, clarify, refused, unanswerable, error),
`answer`, `result_columns`, `result_rows`, `clarify_question`, `sql`,
`models`, `lineage`, `freshness`, `cost_usd`, `trace_id`, `thread_id`. A
`clarify` result has no trace yet; resume the thread with the user's answer.

The role comes **only from the token**. A `role` field in a body is a 422.
Threads and traces are visible only to the role that created them; other
roles get a 404. Errors are `{error, code}` JSON with no stack trace, and no
response repeats the question.

## Tokens

`GOVERNOR_API_TOKENS` holds comma-separated `role:token` pairs:

```
GOVERNOR_API_TOKENS=analyst:<long random string>,finance_admin:<another one>
```

* Every role must exist in `knowledge/access.yaml`, or the app refuses to start.
* Several tokens may map to the same role.
* Generate tokens with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
* Tokens are compared in constant time (`hmac.compare_digest`) and are never logged.
* Keep them in `.env` (git-ignored). `.env.example` has placeholders only.

Clients send `Authorization: Bearer <token>`.

## Run locally with uvicorn

```
uv run python fixture/build_green.py                      # once: warehouse
uv run python -m governor.core.harvest artifacts/green --out artifacts/meta.duckdb
uv run python -m governor.ask.catalog build

# PowerShell
$env:GOVERNOR_API_TOKENS = "analyst:<token>"
$env:GOVERNOR_LLM = "fake"                                 # offline; or openrouter + OPENROUTER_API_KEY
uv run uvicorn governor.api.app:app --port 8000

curl -s localhost:8000/health
curl -s -X POST localhost:8000/v1/ask -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" -d '{"question": "how many accounts are there"}'
```

`GOVERNOR_LLM`: `openrouter` (default, real models, needs `OPENROUTER_API_KEY`),
`fake` (offline FakeLLM, answers with a placeholder query), or
`fake:SCRIPT.json` (scripted replies, see `governor.ask.llm_testing`).

## Run with Docker Compose

```
cp .env.example .env        # then fill in tokens (and the key for openrouter)
docker compose up --build api
```

The image build runs `fixture/build_green.py`, the harvester and
`python -m governor.ask.catalog build`, so the warehouse, metadata store and
catalog cards are baked into the image and opened read-only. The `ui` service
(Streamlit, port 8501) is a placeholder until G8.

## State volume

All writable state lives in one folder, `GOVERNOR_STATE_DIR` (`/data` in the
image, `artifacts/` by default locally):

* `traces.duckdb`: decision traces (redacted: question hash and length, PII masked);
* `checkpoints.sqlite`: LangGraph checkpoints for paused (clarify) threads.

Compose mounts the named volume `governor-data` on `/data`. The container
runs as a non-root user that can write only there. Note that checkpoints hold
the raw question, the clarification and result rows (including granted
emails); treat the volume as sensitive and delete it to forget threads.

## Where to host it (choice waits for the capstone brief)

Any host that runs one container with a small persistent disk works. The
service keeps state in SQLite and DuckDB files, so it must run as **one
instance**; it cannot scale out across replicas.

| host | persistent `/data` | cost / effort | notes |
|---|---|---|---|
| A small VM (Hetzner, DigitalOcean, EC2) | local disk | cheapest at steady use; you patch the OS and set up TLS (Caddy) | most control, compose works as-is |
| Fly.io | Fly volume on one machine | low; `fly launch` from the Dockerfile | volume is pinned to one machine/region; free TLS |
| Render | persistent disk (paid plans) | low; deploy from the repo | a disk blocks zero-downtime deploys; free tier has no disk |
| Cloud Run | volume via Cloud Storage FUSE or NFS | pay per request, scales to zero | file locks on FUSE are unreliable for SQLite/DuckDB; set max instances to 1 |

Leaning: a VM or Fly.io (real block storage, one instance). Cloud Run fits
only if traces move to a managed database. Decide once the brief is known.
