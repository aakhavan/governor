"""E3 acceptance: perturbed test bed tooling (sample only), generic loader, build_eval --policy."""
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
    r = run(["git", "diff", "--quiet", "main", "--", "testbed/load_olist.py"])
    check("testbed/load_olist.py unchanged against main", r.returncode == 0, "the file differs from main")
    readme = (ROOT / "testbed/README.md").read_text(encoding="utf-8")
    check("README has the perturbed holdout section", "perturbed holdout" in readme.lower(), "")
    check("README states the Olist licence", "CC BY-NC-SA 4.0" in readme and "TODO (licence)" not in readme, "")
    tracked = run(["git", "ls-files", "testbed/data"]).stdout.strip()
    check("no real data tracked", tracked == "", tracked[:200])
    r = run([sys.executable, "-m", "governor.eval.build_eval", "--help"])
    check("build_eval has --policy", "--policy" in (r.stdout or ""), "")


def perturb_twice():
    import filecmp
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        outs = [Path(tmp) / "a", Path(tmp) / "b"]
        for out in outs:
            r = run([sys.executable, "testbed/perturb.py", "--source", "testbed/sample", "--out", str(out),
                     "--policy", "knowledge/shop/policy.yaml"])
            if not check(f"perturb.py runs on the sample ({out.name})", r.returncode == 0, (r.stderr or r.stdout)[-200:]):
                return
        names = sorted(p.name for p in outs[0].iterdir())
        check("mapping.json, policy.yaml and the junk table are written",
              {"mapping.json", "policy.yaml", "etl_audit_log.csv"} <= set(names), ", ".join(names))
        same = all(filecmp.cmp(outs[0] / n, outs[1] / n, shallow=False) for n in names)
        check("two runs give identical files", same and names == sorted(p.name for p in outs[1].iterdir()), "")
        mapping = json.loads((outs[0] / "mapping.json").read_text(encoding="utf-8"))
        old = set(mapping.get("tables", {}))
        new = set(mapping.get("tables", {}).values())
        check("every sample table is renamed", bool(old) and not (old & new)
              and not any((outs[0] / f"{t}.csv").exists() for t in old), "")


guarded("static", static)
guarded("perturb", perturb_twice)
pytest_check("tests/testbed", required=[
    "test_perturb_is_deterministic", "test_no_original_table_or_column_name_survives",
    "test_values_and_row_counts_are_unchanged", "test_orders_split_keeps_every_order",
    "test_policy_is_renamed_through_the_mapping", "test_junk_table_is_written",
    "test_loader_refuses_a_non_empty_raw_without_replace", "test_loader_builds_safe_statements"])
pytest_check("tests/eval", required=["test_build_eval_policy_option_reaches_the_hooks"])
finish("E3")
