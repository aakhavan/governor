"""F3 acceptance: Up-to-date runs and drift-aware design (docs/capstone/batch3.md section 29)."""
import os
import sys
# Pin every test-bed setting to the (empty) acceptance port so live tests skip instead of running against
# whatever database the calling shell points at.
for _k, _v in {"GOVERNOR_PG_PORT": "55433", "GOVERNOR_PG_HOST": "localhost"}.items():
    os.environ[_k] = _v
for _k in ("GOVERNOR_PG_DSN", "GOVERNOR_PG_ADMIN_DSN", "GOVERNOR_BUILD_DSN", "GOVERNOR_BUILD_PASSWORD", "GOVERNOR_DEPLOY_PASSWORD",
           "GOVERNOR_ROOT", "GOVERNOR_TENANTS", "GOVERNOR_SLACK_TARGETS", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"):
    os.environ.pop(_k, None)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import re  # noqa: E402
from _common import ROOT, check, finish, guarded, pytest_check, run  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def _has(rel: str, needle: str) -> bool:
    p = ROOT / rel
    return p.is_file() and needle in p.read_text(encoding="utf-8")


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    check('compare node', _has('src/governor/build/graph.py', 'up_to_date'), "missing in src/governor/build/graph.py")
    check('force flag', _has('src/governor/build/__main__.py', '--force'), "missing in src/governor/build/__main__.py")
    check('drift section in report', _has('src/governor/build/design.py', 'Drift since the last approved build'), "missing in src/governor/build/design.py")


def required_present(names: list[str]) -> None:
    c = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests"], timeout=300)
    found = set(re.findall(r"::(test_[A-Za-z0-9_]+)", c.stdout))
    missing = [t for t in names if t not in found]
    check("required tests present", not missing, f"missing: {missing}" if missing else f"{len(names)} found")


guarded("static", static)
pytest_check("tests/build")
pytest_check("tests/integrations")
required_present(['test_unchanged_target_is_up_to_date_without_model_calls', 'test_failed_last_build_is_not_up_to_date', 'test_force_runs_full_design', 'test_drift_passes_previous_design_and_note', 'test_design_report_lists_drift', 'test_target_without_fingerprint_runs_as_before', 'test_slack_run_force_parses', 'test_slack_up_to_date_message'])
finish("F3")
