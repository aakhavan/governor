"""G6a acceptance: graph shape (no network), prompts free of golden text and wall-clock dates, required offline tests."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, golden_leaks, grep, guarded, py_json, pytest_check, run, tail  # noqa: E402

NODES = ["guard", "retrieve_context", "plan", "clarify", "draft_sql", "validate", "dry_run", "repair", "execute",
         "answer", "record_trace"]
TRACE = ["trace_id", "ts", "role", "question_hash", "question_len", "retrieved_ids", "plan_json", "sql_attempts",
         "policy_decisions", "executed_sql", "row_count", "result_hash", "answer", "outcome", "models", "tokens_in",
         "tokens_out", "cost_usd", "latency_s", "human_feedback"]
TESTS = ["test_clarify_interrupt_and_resume", "test_repair_then_success", "test_repair_exhausted_refuses",
         "test_policy_refusal_analyst", "test_pii_masked_finance_admin", "test_answer_numbers_come_from_result",
         "test_guard_blocks_injection", "test_volatile_time_never_reaches_execute"]
PROMPTS = ["plan.md", "draft_sql.md", "repair.md", "answer.md"]


def graph_shape():
    data, err = py_json("import json; from governor.ask.graph import build_graph\n"
                        "g = build_graph(llm=None)\n"
                        "print(json.dumps(sorted(n for n in g.get_graph().nodes if not n.startswith('__'))))", timeout=120)
    if check("build_graph(llm=None) compiles without network", data is not None, err):
        check("graph has exactly the specified nodes", sorted(NODES) == data, f"got {data}")


def traces():
    data, err = py_json("import json; from governor.ask.traces import TRACE_COLUMNS; print(json.dumps(list(TRACE_COLUMNS)))")
    if check("governor.ask.traces.TRACE_COLUMNS importable", data is not None, err):
        miss = [c for c in TRACE if c not in data]
        check("trace row has every specified column", not miss, f"missing: {miss}")


def prompts():
    d = ROOT / "src/governor/ask/prompts"
    miss = [p for p in PROMPTS if not (d / p).is_file()]
    check("graph prompts exist as files", not miss, f"missing: {miss}")
    files = [f for f in d.glob("*.md")] + [f for f in (ROOT / "src/governor/ask").rglob("*.py")] + \
            [f for f in (ROOT / "tests").rglob("*.py")]
    bad = golden_leaks(files)
    check("no golden questions or gold SQL in prompts, code or tests", not bad, ", ".join(bad[:5]))
    hits = [h for h in grep(["src/governor/ask"], r"date\.today\(|current_date|current_timestamp|\bnow\(\)")]
    check("no wall-clock dates in ask logic (as_of only)", not hits, ", ".join(hits[:5]))


def agent_system():
    tmp = Path(tempfile.mkdtemp(prefix="g6-accept-"))
    r = run([sys.executable, "-m", "governor.eval.run", "--system", "agent", "--split", "tune", "--llm", "fake",
             "--out", str(tmp), "--holdout-log", str(tmp / "h.log")], timeout=900)
    f = tmp / "agent-tune.json"
    ok = r.returncode == 0 and f.is_file()
    if check("agent system runs through the harness on the FakeLLM", ok, tail(r)):
        rep = json.loads(f.read_text(encoding="utf-8"))
        check("agent report covers the 25 tune items", len(rep["items"]) == 25, len(rep["items"]))


guarded("graph", graph_shape)
guarded("prompts", prompts)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests/ask", required=TESTS)
finish("G6a")
