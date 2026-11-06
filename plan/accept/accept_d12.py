"""D12 acceptance: clean-up fixes from the D6 and D8 gate reviews, each with its named test."""
import sys
import os
# Pin every test-bed setting to the (empty) acceptance port so live tests skip instead of running against
# whatever database the calling shell points at (the dev test bed with real Olist data, 6 Nov 2026).
for _k, _v in {"GOVERNOR_PG_PORT": "55433", "GOVERNOR_PG_HOST": "localhost"}.items():
    os.environ[_k] = _v
for _k in ("GOVERNOR_PG_DSN", "GOVERNOR_PG_ADMIN_DSN", "GOVERNOR_BUILD_DSN", "GOVERNOR_BUILD_PASSWORD", "GOVERNOR_DEPLOY_PASSWORD"):
    os.environ.pop(_k, None)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import finish, guarded, pytest_check  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402
from _common import check  # noqa: E402


def frozen():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)


guarded("frozen", frozen)
pytest_check("tests/build", required=["test_certify_registry_written_after_serving", "test_events_drop_nested_values",
                                      "test_empty_salt_rejected_early"])
pytest_check("tests/eval", required=["test_certified_eval_report_redacted", "test_build_eval_blueprint_breakdown",
                                     "test_build_eval_valid_first_try_recorded"])
finish("D12")
