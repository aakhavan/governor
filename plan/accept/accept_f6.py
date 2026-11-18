"""F6 acceptance: One Slack bot for several tenants (docs/capstone/batch3.md section 32)."""
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
    check('registry in Slack config', _has('src/governor/integrations/slack/config.py', 'GOVERNOR_TENANTS'), "missing in src/governor/integrations/slack/config.py")
    check('tenants doc', _has('docs/tenants.md', 'tenants:'), "missing in docs/tenants.md")


def required_present(names: list[str]) -> None:
    # Collect the step's folders by name: pytest skips folders called "build" when collecting from "tests".
    c = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/integrations"], timeout=300)
    found = set(re.findall(r"::(test_[A-Za-z0-9_]+)", c.stdout))
    missing = [t for t in names if t not in found]
    check("required tests present", not missing, f"missing: {missing}" if missing else f"{len(names)} found")


guarded("static", static)
pytest_check("tests/integrations")
pytest_check("tests")
pytest_check("tests/build")  # not reached by "tests": pytest skips folders named build
required_present(['test_targets_come_from_tenant_registry', 'test_run_routes_to_its_tenant', 'test_approve_resolves_tenant_from_thread', 'test_thread_in_two_tenants_is_a_usage_error', 'test_ask_refused_in_multi_tenant_mode', 'test_messages_name_the_tenant'])
finish("F6")
