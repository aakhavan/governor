"""D11 acceptance: red-team detector ignores governor's own catalogue vocabulary and matches case-insensitively;
certified answers drop irrelevant filters and answer ratio KPIs over long periods with monthly values."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import check, finish, guarded, pytest_check  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def frozen():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)


guarded("frozen", frozen)
pytest_check("tests/eval", required=["test_leak_ignores_catalogue_vocabulary", "test_leak_matching_case_insensitive"])
pytest_check("tests/ask", required=["test_irrelevant_filter_ignored", "test_ratio_kpi_multi_period_answers_monthly"])
finish("D11")
