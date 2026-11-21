"""V4 acceptance: React console with the live run canvas (docs/capstone/batch4.md section 37)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import (APP, deps_present, env_clean, front_end_checks, no_tracked_build_output,  # noqa: E402
                      scripts_present, test_titles_present)

env_clean()
from _common import check, finish, guarded  # noqa: E402


def static():
    deps_present(["react", "react-dom", "@xyflow/react", "@dagrejs/dagre", "recharts", "react-router-dom", "vite",
                  "typescript", "vitest", "eslint"])
    scripts_present(["dev", "build", "preview", "lint", "typecheck", "test"])
    for rel in ("src/run/fold.ts", "src/graph/RunCanvas.tsx", "src/graph/GovernorNode.tsx", "src/copy.ts",
                "src/pages/RunsPage.tsx", "src/pages/RunPage.tsx", "src/pages/GraphPage.tsx", "package-lock.json"):
        check(f"apps/console/{rel}", (APP / rel).is_file(), "missing")
    no_tracked_build_output()
    tests = "".join(p.read_text(encoding="utf-8", errors="replace") for p in (APP / "src").rglob("*.test.ts*"))
    check("fold test reads the shared cases", "fold_cases.json" in tests, "fold_cases.json not imported in a test")
    test_titles_present(["fold parity", "GovernorNode states", "useRunEvents dedupe and reconnect", "RunPage renders demo run"])


guarded("static", static)
front_end_checks()
finish("V4")
