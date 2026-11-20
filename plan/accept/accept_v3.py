"""V3 acceptance: console API, demo runs, LangGraph Studio entry points (docs/capstone/batch4.md section 36)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import env_clean  # noqa: E402

env_clean()
os.environ.pop("OPENROUTER_API_KEY", None)  # studio graphs must compile offline with the fake LLM
from _common import ROOT, check, finish, guarded, py_json, pytest_check  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    try:
        lg = json.loads((ROOT / "langgraph.json").read_text(encoding="utf-8"))
        g = lg.get("graphs", {})
        check("langgraph.json graphs", set(g) >= {"build", "ask"} and "env" not in lg, str(g)[:200])
    except (OSError, ValueError) as exc:
        check("langgraph.json", False, type(exc).__name__)
    demo = ROOT / "src/governor/integrations/console/demo"
    runs = list(demo.rglob("*.jsonl"))
    arts = list(demo.rglob("*.artifacts.json"))
    check("demo runs shipped", len(runs) >= 4 and len(arts) >= 1, f"{len(runs)} runs, {len(arts)} artifacts")
    check("demo script", (ROOT / "scripts/make_console_demo.py").is_file(), "missing")


def studio():
    data, err = py_json("import json; from governor.integrations import studio; "
                        "b = studio.build(); a = studio.ask(); "
                        "print(json.dumps({'b': sorted(b.get_graph().nodes), 'a': sorted(a.get_graph().nodes), "
                        "'cp': [getattr(b, 'checkpointer', None) is None, getattr(a, 'checkpointer', None) is None]}))")
    if data is None:
        check("studio graphs compile offline", False, err)
        return
    check("studio build graph", "design_gate" in data["b"], f"{len(data['b'])} nodes")
    check("studio ask graph", "validate" in data["a"], f"{len(data['a'])} nodes")
    check("studio graphs without checkpointer", all(data["cp"]), str(data["cp"]))


guarded("static", static)
guarded("studio", studio)
pytest_check("tests/api", ["test_console_requires_token", "test_console_open_mode_allows_reads_only", "test_console_graph_topology",
                           "test_console_runs_lists_live_and_demo", "test_console_run_view_matches_fold",
                           "test_console_sse_frames_and_last_event_id", "test_console_replay_pacing_capped",
                           "test_console_live_tail_ends_on_run_finished", "test_console_artifacts_names_and_counts_only",
                           "test_console_artifacts_missing_inputs", "test_ask_routes_unchanged_with_console"])
pytest_check("tests/integrations", ["test_demo_runs_deterministic", "test_demo_runs_cover_required_cases",
                                    "test_studio_graphs_compile_offline"])
pytest_check("tests")
pytest_check("tests/build")
finish("V3")
