"""D14 acceptance: staging keys checked against the profile's candidate keys, with the named tests."""
import sys
import os
# Pin every test-bed setting to the (empty) acceptance port so live tests skip instead of running against
# whatever database the calling shell points at.
for _k, _v in {"GOVERNOR_PG_PORT": "55433", "GOVERNOR_PG_HOST": "localhost"}.items():
    os.environ[_k] = _v
for _k in ("GOVERNOR_PG_DSN", "GOVERNOR_PG_ADMIN_DSN", "GOVERNOR_BUILD_DSN", "GOVERNOR_BUILD_PASSWORD", "GOVERNOR_DEPLOY_PASSWORD",
           "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"):
    os.environ.pop(_k, None)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, pytest_check  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    src = (ROOT / "src/governor/build/design.py").read_text(encoding="utf-8")
    check("KEY_NOT_UNIQUE is a validation code", "KEY_NOT_UNIQUE" in src, "missing")
    check("propose prompt mentions candidate keys",
          "candidate_keys" in (ROOT / "src/governor/build/prompts/propose.md").read_text(encoding="utf-8"), "missing")


guarded("static", static)
pytest_check("tests/build", required=["test_key_not_unique_flags_non_candidate_key", "test_key_superset_of_candidate_key_is_accepted",
                                      "test_key_on_table_without_candidate_key_is_flagged", "test_computed_key_is_flagged",
                                      "test_design_repair_fixes_key_before_the_gate"])
finish("D14")
