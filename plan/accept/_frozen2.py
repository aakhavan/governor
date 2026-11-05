"""Hash check for the capstone ground truth (evaluation/FROZEN_CAPSTONE.sha256). Stdlib only."""
from __future__ import annotations

from _common import ROOT, sha256


def frozen_capstone_ok() -> tuple[bool, str]:
    f = ROOT / "evaluation" / "FROZEN_CAPSTONE.sha256"
    if not f.is_file():
        return False, "evaluation/FROZEN_CAPSTONE.sha256 missing"
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        h, name = line.split(maxsplit=1)
        p = ROOT / name.strip().lstrip("*")
        if not p.is_file() or sha256(p) != h:
            return False, f"{name.strip()} does not match its frozen hash"
    return True, "capstone ground truth unchanged"
