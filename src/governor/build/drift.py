"""Profile fingerprint and drift (batch3.md section 28).

A fingerprint is the shape of the raw schema at approval: table and column names, ``inferred_type``, ``pii`` and
``candidate_keys``. It never holds row counts, null rates, distinct counts, min, max or relationship coverage, so it
carries no data values. ``diff`` compares two fingerprints and names what changed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from governor.build.models import Profile

VERSION = 1


def fingerprint(profile: Profile | dict) -> dict:
    """The sorted, value-free shape of ``profile`` (a ``Profile`` or its section 5 dict)."""
    p = profile if isinstance(profile, Profile) else Profile.model_validate(profile)
    tables: dict[str, Any] = {}
    for t in sorted(p.tables, key=lambda t: t.name):
        tables[t.name] = {
            "columns": {c.name: {"type": c.inferred_type, "pii": bool(c.pii)}
                        for c in sorted(t.columns, key=lambda c: c.name)},
            "candidate_keys": sorted(sorted(k) for k in t.candidate_keys),
        }
    return {"version": VERSION, "schema": p.schema_, "tables": tables}


def fingerprint_hash(fp: dict) -> str:
    """sha256 of the canonical JSON (sorted keys, no whitespace)."""
    canon = json.dumps(fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class Drift(BaseModel):
    """What changed between two fingerprints; names only."""

    model_config = ConfigDict(extra="forbid")

    tables_added: list[str] = Field(default_factory=list)
    tables_removed: list[str] = Field(default_factory=list)
    columns_added: dict[str, list[str]] = Field(default_factory=dict)
    columns_removed: dict[str, list[str]] = Field(default_factory=dict)
    type_changes: dict[str, dict[str, list[str]]] = Field(default_factory=dict)  # table -> column -> [old, new]
    pii_changes: dict[str, list[str]] = Field(default_factory=dict)
    keys_changed: list[str] = Field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.tables_added or self.tables_removed or self.columns_added or self.columns_removed
                    or self.type_changes or self.pii_changes or self.keys_changed)

    def summary_lines(self) -> list[str]:
        """One plain line per change, sorted."""
        lines = [f"table added: {t}" for t in self.tables_added]
        lines += [f"table removed: {t}" for t in self.tables_removed]
        lines += [f"column added: {t}.{c}" for t, cs in self.columns_added.items() for c in cs]
        lines += [f"column removed: {t}.{c}" for t, cs in self.columns_removed.items() for c in cs]
        lines += [f"type changed: {t}.{c} {old} -> {new}"
                  for t, cs in self.type_changes.items() for c, (old, new) in cs.items()]
        lines += [f"pii changed: {t}.{c}" for t, cs in self.pii_changes.items() for c in cs]
        lines += [f"candidate keys changed: {t}" for t in self.keys_changed]
        return sorted(lines)


def diff(old: dict, new: dict) -> Drift:
    """The drift from fingerprint ``old`` to fingerprint ``new``."""
    ot, nt = old.get("tables") or {}, new.get("tables") or {}
    d = Drift(tables_added=sorted(set(nt) - set(ot)), tables_removed=sorted(set(ot) - set(nt)))
    for name in sorted(set(ot) & set(nt)):
        oc, nc = ot[name].get("columns") or {}, nt[name].get("columns") or {}
        if added := sorted(set(nc) - set(oc)):
            d.columns_added[name] = added
        if removed := sorted(set(oc) - set(nc)):
            d.columns_removed[name] = removed
        common = sorted(set(oc) & set(nc))
        types = {c: [oc[c].get("type"), nc[c].get("type")] for c in common if oc[c].get("type") != nc[c].get("type")}
        if types:
            d.type_changes[name] = types
        if pii := [c for c in common if bool(oc[c].get("pii")) != bool(nc[c].get("pii"))]:
            d.pii_changes[name] = pii
        okeys = sorted(sorted(k) for k in ot[name].get("candidate_keys") or [])
        nkeys = sorted(sorted(k) for k in nt[name].get("candidate_keys") or [])
        if okeys != nkeys:
            d.keys_changed.append(name)
    return d


__all__ = ["Drift", "VERSION", "diff", "fingerprint", "fingerprint_hash"]
