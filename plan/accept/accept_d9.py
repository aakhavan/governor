"""D9 acceptance: Slack app as a thin client with strict commands, an approver allowlist, in-place progress and a
design card; build never imports Slack; no data values in payloads."""
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
    check("slack-bolt is a dependency", "slack-bolt" in (ROOT / "pyproject.toml").read_text(encoding="utf-8"), "")
    for rel in ("src/governor/integrations/slack/app.py", "src/governor/integrations/slack/blocks.py",
                "src/governor/integrations/slack/notifier.py", "docs/slack.md"):
        check(f"{rel} exists", (ROOT / rel).is_file(), "missing")
    check("governor.build never imports Slack", not grep(["src/governor/build"], r"^\s*(import|from)\s+\S*slack"), "")
    d, err = py_json("import json, governor.integrations.slack.blocks as b, governor.integrations.slack.notifier as n\nprint(json.dumps({'ok': True}))")
    check("Slack modules import without tokens", d is not None, err)


guarded("static", static)
pytest_check("tests/integrations", required=["test_command_parsing_is_strict", "test_non_approver_cannot_approve",
                                             "test_approve_button_calls_graph_with_mapped_name", "test_progress_message_updates_in_place",
                                             "test_design_card_has_counts_gaps_and_buttons", "test_notifier_failure_never_breaks_a_build",
                                             "test_no_data_values_in_slack_payloads"])
pytest_check("tests/build")
finish("D9")
