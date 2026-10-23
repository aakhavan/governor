# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G4 is in place. Catalog cards are built from meta.duckdb and knowledge/metrics.yaml: 4 model cards (dim_accounts, fct_invoices, fct_revenue_daily, mrr_monthly) and 10 metric cards in artifacts/catalog_cards.jsonl. Each card has id, kind, name, text, tables, and pii_columns. dim_accounts lists contact_email and contact_name as PII. Metric cards name the physical tables their SQL reads, with CTE names and schemas removed, and they do not contain the SQL. governor.ask.retrieval.search does BM25 with snake_case tokens, dense search over artifacts/card_embeddings.npz, and RRF with k=60. Eval scores the mean share of gold-SQL tables in the top-k hits through governor.eval.golden. On the tune split that is n=18, BM25 recall@3 is 0.8333 and hybrid with the fake embedder is 0.8056. The golden set is still frozen (40 questions, tune 25, holdout 15). as_of remains 2026-10-22.

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

## G4 result (implementer notes)
`governor.ask.catalog` builds 14 cards (4 allowlisted models + 10 metrics) from meta.duckdb, access.yaml and metrics.yaml into artifacts/catalog_cards.jsonl. Model cards list the metrics that read them (from metrics.yaml SQL). Grain is the description's "One row per ..." phrase, else the unique-tested column. `governor.ask.retrieval.search` does bm25/dense/hybrid. Hybrid fuses with `governor.core.retrieval.rrf` (k=60, each list depth max(10, k)). No chromadb: dense uses numpy over artifacts/card_embeddings.npz, keyed by embedder name plus card texts. The default embedder is core.llm.get_embeddings (EMBED_MODEL still a guess, not run); `fake` is HashEmbedder. Tune recall@3: bm25 0.8333, hybrid(fake) 0.8056, dense(fake) 0.7778 (n=18). The fake hybrid score says nothing about real embeddings. Acceptance: 16/16. Full pytest: 163 passed. The test file is tests/ask/test_cards_retrieval.py, because tests/ask/test_retrieval.py clashed with tests/core/test_retrieval.py (no __init__.py).

## G4 result
*Catalog and metric cards, hybrid schema retrieval, recall@k on gold tables, 23 Oct 2026 15:56.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G4`.

| check | ok | detail |
|---|---|---|
| catalog build exits 0 | yes | {"out": "C:\\Users\\amir0\\portfolio\\governor\\artifacts\\catalog_cards.jsonl", "cards": 14, "model": 4, "metric": 10} |
| every card has the required fields | yes | 14 cards |
| one model card per allowlisted model, nothing else | yes | ['dim_accounts', 'fct_invoices', 'fct_revenue_daily', 'mrr_monthly'] |
| one metric card per metrics.yaml entry | yes | missing: [] |
| dim_accounts card lists its PII columns | yes |  |
| metric cards list the tables their SQL uses | yes |  |
| no golden questions or gold SQL in cards or code | yes |  |
| retrieval.search runs | yes |  |
| 'monthly recurring revenue' finds mrr_monthly in top 3 | yes | ['mrr_monthly'] |
| snake_case split: 'days outstanding' finds fct_invoices in top 3 | yes | ['fct_invoices'] |
| retrieval eval (bm25) runs | yes | {"mode": "bm25", "k": 3, "n": 18, "recall": 0.8333} |
| eval counts only tune questions with gold SQL | yes | n=18, expected 18 |
| bm25 recall@3 on gold tables >= 0.80 | yes | recall=0.8333 |
| hybrid eval runs with the fake embedder | yes | {"mode": "hybrid", "k": 3, "n": 18, "recall": 0.8056} |
| golden set still frozen | yes | golden set unchanged |
| pytest tests/ask | yes | 15 passed in 3.88s |

Review: Catalog and metric cards are built from meta.duckdb and metrics.yaml (4 models, 10 metrics). Card text is schema and metric definitions; golden questions and gold SQL are absent. Recall@3 is the mean share of tables parsed from gold_sql that appear on the top-k hits: BM25 0.8333 (n=18) and hybrid with HashEmbedder 0.8056. A fake meta store supplies the unit tests, so a hardcoded catalog cannot pass.

For Amir: Hybrid recall is reported and not gated; only BM25 must be at least 0.80. The probe days outstanding also matches prose on the overdue definition and the invoice column description, so test_tokens_split_snake_case is what locks the splitter. search() with embedder None calls the configured embedding model and will use the network.

## Additions for G5a
Cards in artifacts/catalog_cards.jsonl (4 models, then 10 metrics). Fields: id, kind, name, text, tables, pii_columns. Ids model:{name} and metric:{id}. Models: dim_accounts, fct_invoices, fct_revenue_daily, mrr_monthly. dim_accounts PII: contact_email, contact_name. Model text: description, grain, owner, columns (type, description, pii tag), tests, upstream sources, metrics that read the model. Metric text: label, definition, synonyms, grain, physical tables, time column. sqlglot drops CTEs and schemas. SQL is not on the card. search(query, k=5, mode=hybrid|bm25|dense, embedder=None) returns Hit(card_id, score, tables); join text on id. Hybrid: depth max(10, k), RRF k=60, then top k. embedder None uses get_embeddings (network unless EMBED_BACKEND=local). Offline: embedder fake or HashEmbedder. Cache: artifacts/card_embeddings.npz. Eval: python -m governor.ask.retrieval eval --split tune --mode bm25|hybrid --k 3 --embedder fake. Mean share of gold-SQL tables in top-k hits. Tune n=18. BM25 0.8333. Hybrid+fake 0.8056, ungated. Snake_case tokens keep the word and its parts. Do not copy questions or gold SQL into prompts or cards. as_of is 2026-10-22.
