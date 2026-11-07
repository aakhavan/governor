"""D9b acceptance: Slack terminal states, runner allowlist, design upload without mappings, PR link in the event."""
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
    check("GOVERNOR_SLACK_RUNNERS documented", "GOVERNOR_SLACK_RUNNERS" in (ROOT / "docs/slack.md").read_text(encoding="utf-8"), "missing")
    check("no 'Run finished at' reply", not grep(["src/governor/integrations"], r"Run finished at"), "still there")
    d, err = py_json("import json, governor.integrations.slack.blocks as b, governor.integrations.slack.notifier as n\nprint(json.dumps({'ok': True}))")
    check("Slack modules import without tokens", d is not None, err)


guarded("static", static)
pytest_check("tests/integrations", required=["test_escalation_marks_progress_failed", "test_escalation_reason_names_failing_tests",
                                             "test_new_run_supersedes_open_thread", "test_startup_marks_interrupted_threads",
                                             "test_no_finished_reply_at_the_gate", "test_non_runner_cannot_start_a_build",
                                             "test_design_upload_omits_mappings"])
pytest_check("tests/build")
finish("D9b")
