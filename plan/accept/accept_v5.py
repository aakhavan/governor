"""V5 acceptance: result views (docs/capstone/batch4.md section 38)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import APP, env_clean, front_end_checks, test_titles_present  # noqa: E402

env_clean()
from _common import check, finish, guarded  # noqa: E402


def static():
    for name in ("SummaryView", "LineageView", "FunnelView", "KpiEvidenceView", "GuardPathView"):
        check(f"view {name}", (APP / "src/views" / f"{name}.tsx").is_file(), "missing")
    test_titles_present(["SummaryView renders", "LineageView renders", "FunnelView renders", "KpiEvidenceView renders",
                         "GuardPathView renders", "empty state", "captions come from copy"])


guarded("static", static)
front_end_checks()
finish("V5")
