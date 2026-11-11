"""E1 acceptance: /governor ask as a thin client of the certified path."""
import sys
import os
# Pin every test-bed setting to the (empty) acceptance port so live tests skip instead of running against
# whatever database the calling shell points at.
for _k, _v in {"GOVERNOR_PG_PORT": "55433", "GOVERNOR_PG_HOST": "localhost"}.items():
    os.environ[_k] = _v
for _k in ("GOVERNOR_PG_DSN", "GOVERNOR_PG_ADMIN_DSN", "GOVERNOR_BUILD_DSN", "GOVERNOR_BUILD_PASSWORD", "GOVERNOR_DEPLOY_PASSWORD",
           "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "GOVERNOR_MCP_ROLE"):
    os.environ.pop(_k, None)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, py_json, pytest_check, run  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    check("governor.build imports neither Slack nor ask",
          not grep(["src/governor/build"], r"^\s*(import|from)\s+\S*(slack|governor\.ask)"), "")
    check("governor.ask never imports integrations", not grep(["src/governor/ask"], r"^\s*(import|from)\s+governor\.integrations"), "")
    check("no top-level import of governor.ask in the Slack modules",
          not grep(["src/governor/integrations"], r"^(import|from)\s+governor\.ask"), "import it inside the default asker")
    d, err = py_json("import json, governor.integrations.slack.app as a, governor.integrations.slack.blocks as b\n"
                     "print(json.dumps({'ok': True, 'usage': 'ask' in b.USAGE}))")
    check("Slack modules import without tokens or a database", d is not None, err)
    check("usage text lists ask", bool(d and d.get("usage")), "")
    doc = (ROOT / "docs/slack.md").read_text(encoding="utf-8")
    for word in ("/governor ask", "GOVERNOR_SLACK_ASK_ROLE", "GOVERNOR_SLACK_ASKERS", "GOVERNOR_SLACK_ASK_LLM"):
        check(f"docs/slack.md mentions {word}", word in doc, "")


guarded("static", static)
pytest_check("tests/integrations", required=[
    "test_ask_parses_the_whole_question", "test_ask_needs_a_question_of_sane_length",
    "test_ask_posts_the_certified_answer_in_the_channel", "test_ask_not_available_shows_the_gap_text",
    "test_ask_refusal_is_ephemeral_without_the_question", "test_ask_error_is_scrubbed_and_ephemeral",
    "test_ask_requires_an_asker", "test_ask_role_comes_from_config_only", "test_ask_role_must_be_a_reader_role"])
finish("E1")
