"""D12 acceptance: clean-up fixes from the D6 and D8 gate reviews, each with its named test."""
import sys
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
