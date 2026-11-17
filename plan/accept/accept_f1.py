"""F1 acceptance: Safety rails (docs/capstone/batch3.md section 27)."""
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
    check('pgconn helper exists', _has('src/governor/core/pgconn.py', 'def with_timeout'), "missing in src/governor/core/pgconn.py")
    check('build_dsn uses the timeout', _has('src/governor/build/workspace.py', 'with_timeout'), "missing in src/governor/build/workspace.py")
    check('dbt profile template has connect_timeout', _has('src/governor/build/workspace.py', 'connect_timeout'), "missing in src/governor/build/workspace.py")
    r = run(["git", "diff", "--name-only", "main", "--", "src/governor/eval"])
    check("src/governor/eval untouched", r.returncode == 0 and not r.stdout.strip(), r.stdout.strip()[:200])


def required_present(names: list[str]) -> None:
    # Collect the step's folders by name: pytest skips folders called "build" when collecting from "tests".
    c = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/core", "tests/build", "tests/integrations"], timeout=300)
    found = set(re.findall(r"::(test_[A-Za-z0-9_]+)", c.stdout))
    missing = [t for t in names if t not in found]
    check("required tests present", not missing, f"missing: {missing}" if missing else f"{len(names)} found")


guarded("static", static)
pytest_check("tests/core")
pytest_check("tests/build")
pytest_check("tests/integrations")
required_present(['test_with_timeout_adds_connect_timeout_once', 'test_build_dsn_has_connect_timeout', 'test_unreachable_database_fails_within_timeout', 'test_dbt_profile_template_has_connect_timeout', 'test_start_line_names_workspace_without_secrets', 'test_usage_footer_names_workspace'])
finish("F1")
