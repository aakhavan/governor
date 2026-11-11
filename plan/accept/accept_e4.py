"""E4 acceptance: threat tests, repair-prompt redaction, threat model."""
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


MARK = "ZZMARKER_7781"


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    for f in ("src/governor/build/graph.py", "src/governor/build/design.py", "src/governor/build/prompts/repair.md",
              "src/governor/build/prompts/propose.md"):
        r = run(["git", "diff", "--quiet", "main", "--", f])
        check(f"{f} unchanged against main", r.returncode == 0, "the file differs from main")
    check("governor.build imports neither Slack nor ask",
          not grep(["src/governor/build"], r"^\s*(import|from)\s+\S*(slack|governor\.ask)"), "")
    code = ("import json\nfrom governor.build.redact import redact_error\n"
            f"t = redact_error('invalid input syntax for type timestamp: \"{MARK}\"\\n'\n"
            f"                 'DETAIL:  Key (customer_id)=({MARK}) already exists.\\n'\n"
            f"                 'column \"order_id\" of relation \"int_orders\" is null near \\'{MARK}\\' at 12345678901',\n"
            "                 {'order_id', 'int_orders'})\n"
            f"print(json.dumps({{'leak': '{MARK}' in t, 'ids': '\"order_id\"' in t and '\"int_orders\"' in t,\n"
            "                  'digits': '12345678901' in t, 'detail': 'DETAIL' in t}))")
    d, err = py_json(code)
    check("redact_error runs", d is not None, err)
    if d:
        check("no data value survives redaction", not d["leak"], "")
        check("known identifiers survive", d["ids"], "")
        check("long numbers and DETAIL lines go", not d["digits"] and not d["detail"], "")
    tm = ROOT / "docs/capstone/threat-model.md"
    text = tm.read_text(encoding="utf-8") if tm.is_file() else ""
    check("threat model exists, at most 80 lines", bool(text) and len(text.splitlines()) <= 80, f"{len(text.splitlines())} lines")
    for word in ("ASI01", "ASI02", "ASI03", "ASI06", "ASI09", "Open findings"):
        check(f"threat model has {word}", word in text, "")
    check("threat model holds no marker or data value", MARK not in text, "")


guarded("static", static)
pytest_check("tests/build", required=[
    "test_propose_prompt_has_no_data_values", "test_describe_prompt_has_no_data_values",
    "test_instruction_named_column_stays_in_the_profile_block", "test_approved_decision_text_stays_in_its_block",
    "test_hijacked_proposals_get_findings", "test_pii_in_gold_is_an_l7_finding",
    "test_repair_prompt_redacts_data_values", "test_redaction_keeps_known_identifiers",
    "test_redaction_drops_detail_lines_and_long_numbers"])
finish("E4")
