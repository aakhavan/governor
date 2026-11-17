"""F5 acceptance: Tenants: registry, per-tenant build, CLI --tenant (docs/capstone/batch3.md section 31)."""
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
    check('tenancy module', _has('src/governor/core/tenancy.py', 'def load_tenants'), "missing in src/governor/core/tenancy.py")
    check('graph takes a tenant', _has('src/governor/build/graph.py', 'tenant'), "missing in src/governor/build/graph.py")
    check('CLI --tenant', _has('src/governor/build/__main__.py', '--tenant'), "missing in src/governor/build/__main__.py")


def required_present(names: list[str]) -> None:
    # Collect the step's folders by name: pytest skips folders called "build" when collecting from "tests".
    c = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/core", "tests/build"], timeout=300)
    found = set(re.findall(r"::(test_[A-Za-z0-9_]+)", c.stdout))
    missing = [t for t in names if t not in found]
    check("required tests present", not missing, f"missing: {missing}" if missing else f"{len(names)} found")


guarded("static", static)
pytest_check("tests/core")
pytest_check("tests/build")
required_present(['test_tenant_paths_resolve_relative_to_registry', 'test_tenant_registry_rejects_bad_entries', 'test_run_for_tenant_uses_only_its_knowledge', 'test_run_for_tenant_profiles_its_own_database', 'test_tenant_checkpoints_are_separate', 'test_no_tenant_behaviour_unchanged', 'test_cli_tenant_fills_target_and_refuses_mismatch', 'test_certify_refuses_admin_dsn_of_another_tenant'])
finish("F5")
