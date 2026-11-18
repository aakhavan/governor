"""F2 acceptance: Profile fingerprint and drift (docs/capstone/batch3.md section 28)."""
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
    check('drift module exists', _has('src/governor/build/drift.py', 'def fingerprint'), "missing in src/governor/build/drift.py")
    check('diff exists', _has('src/governor/build/drift.py', 'def diff'), "missing in src/governor/build/drift.py")
    check('fingerprint written at approval', _has('src/governor/build/graph.py', 'profile_fingerprint.json'), "missing in src/governor/build/graph.py")
    check('fingerprint published', _has('src/governor/build/publish.py', 'profile_fingerprint'), "missing in src/governor/build/publish.py")


def required_present(names: list[str]) -> None:
    # Collect the step's folders by name: pytest skips folders called "build" when collecting from "tests".
    c = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/build"], timeout=300)
    found = set(re.findall(r"::(test_[A-Za-z0-9_]+)", c.stdout))
    missing = [t for t in names if t not in found]
    check("required tests present", not missing, f"missing: {missing}" if missing else f"{len(names)} found")


guarded("static", static)
pytest_check("tests/build")
required_present(['test_fingerprint_has_no_counts_or_values', 'test_fingerprint_is_stable_across_order', 'test_diff_empty_for_same_profile', 'test_diff_reports_added_and_removed', 'test_diff_reports_type_pii_and_key_changes', 'test_approval_writes_fingerprint'])
finish("F2")
