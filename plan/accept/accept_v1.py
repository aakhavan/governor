"""V1 acceptance: run-event contract, reducer and build-graph tracing (docs/capstone/batch4.md sections 33-35)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import env_clean  # noqa: E402

env_clean()
from _common import ROOT, check, finish, guarded, py_json, pytest_check  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    check("runtrace package", (ROOT / "src/governor/core/runtrace/__init__.py").is_file(), "missing")
    p = ROOT / "tests/fixtures/console/fold_cases.json"
    try:
        cases = json.loads(p.read_text(encoding="utf-8"))
        names = " ".join(c.get("name", "") for c in cases).lower()
        check("fold cases: at least 8", len(cases) >= 8, f"{len(cases)} cases")
        need = ["empty", "repair", "pause", "fail", "duplicate", "up", "cost"]
        miss = [n for n in need if n not in names]
        check("fold cases cover section 34", not miss, f"no case named for: {miss}" if miss else "ok")
    except (OSError, ValueError, AttributeError) as exc:
        check("fold cases file", False, f"{type(exc).__name__}")
    src = (ROOT / "src/governor/build/graph.py").read_text(encoding="utf-8")
    check("build graph wraps nodes", "traced(" in src, "no traced( in build/graph.py")
    check("build does not import ask/integrations", "governor.ask" not in src and "governor.integrations" not in src, "bad import")


def topology():
    data, err = py_json("import json; from governor.core.runtrace.registry import topology; t = topology('build'); "
                        "print(json.dumps({'nodes': [n['id'] for n in t['nodes']], "
                        "'unlabelled': [e for e in t['edges'] if e.get('conditional') and not e.get('label')]}))")
    if data is None:
        check("topology('build')", False, err)
        return
    need = {"profile", "compare", "propose", "validate", "write_report", "design_gate", "record_decisions",
            "write_silver", "dbt_build_silver", "repair_silver", "silver_done", "write_gold", "dbt_build_gold", "summarise"}
    miss = sorted(need - set(data["nodes"]))
    check("topology has every build node", not miss, f"missing: {miss}" if miss else "14 nodes")
    check("every conditional edge labelled", not data["unlabelled"], str(data["unlabelled"])[:200])


guarded("static", static)
guarded("topology", topology)
pytest_check("tests/core", ["test_runlog_appends_and_continues_seq", "test_runlog_never_raises", "test_runtrace_off_writes_nothing",
                            "test_fold_cases", "test_traced_keeps_return_value", "test_interrupt_is_pause_not_failure",
                            "test_failure_records_class_name_only"])
pytest_check("tests/build", ["test_build_registry_matches_graph", "test_build_conditional_edges_labelled",
                             "test_build_run_log_full_run", "test_build_run_log_has_no_data_values", "test_build_events_unchanged"])
pytest_check("tests")
finish("V1")
