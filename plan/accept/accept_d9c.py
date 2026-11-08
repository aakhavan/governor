"""D9c acceptance: next steps and PR button in Slack, decided buttons replaced, schema prefix normalised, live test skip."""
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
from _common import ROOT, check, finish, grep, guarded, py_json, pytest_check  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    check("governor.build never imports Slack", not grep(["src/governor/build"], r"^\s*(import|from)\s+\S*slack"), "")
    check("propose prompt asks for the bare table name",
          "bare" in (ROOT / "src/governor/build/prompts/propose.md").read_text(encoding="utf-8").lower(), "missing")
    d, err = py_json("import json, governor.integrations.slack.blocks as b, governor.integrations.slack.notifier as n\nprint(json.dumps({'ok': True}))")
    check("Slack modules import without tokens", d is not None, err)


guarded("static", static)
pytest_check("tests/integrations", required=["test_built_message_shows_next_step_and_pr_button", "test_pr_button_requires_approver",
                                             "test_published_header_links_pr_and_says_certify", "test_published_without_pr_url_names_branch",
                                             "test_design_buttons_replaced_after_approve", "test_stale_button_press_changes_nothing"])
pytest_check("tests/build", required=["test_schema_prefixed_source_table_is_normalised"])
finish("D9c")
