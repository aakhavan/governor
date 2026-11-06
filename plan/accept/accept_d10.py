"""D10 acceptance: column descriptions from lineage, profile and catalogue, with the named tests."""
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
    check("docs.py exists", (ROOT / "src/governor/build/docs.py").is_file(), "missing")
    check("describe prompt exists", (ROOT / "src/governor/build/prompts/describe.md").is_file(), "missing")


guarded("static", static)
pytest_check("tests/build", required=["test_docs_gold_uses_catalogue_definition", "test_docs_staging_from_lineage_and_profile",
                                      "test_docs_intermediate_inherits_from_refs", "test_docs_llm_fills_the_rest_without_values",
                                      "test_docs_coverage_in_build_summary"])
finish("D10")
