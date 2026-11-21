"""Names and counts from a build target. Missing files become empty lists and nulls.

The response never includes a path, a question, SQL, a cell value or a person's name.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")
_MODEL_LAYER = {"staging", "silver", "gold"}
_LINEAGE_LAYER = {"raw", "silver", "gold", "kpi"}
_KPI_STATUS = {"built", "gap", "declined"}

_catalogue_count: int | None | bool = False


def empty() -> dict:
    return {
        "kpis": [],
        "models": [],
        "tests_passed": None,
        "repairs": None,
        "finding_codes": {},
        "funnel": {"requested": None, "computable": None, "proposed": None, "validated": None, "built": None},
        "lineage": {"nodes": [], "edges": []},
    }


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _catalogue_size() -> int | None:
    global _catalogue_count
    if _catalogue_count is not False:
        return _catalogue_count  # type: ignore[return-value]
    try:
        from governor.core import paths
        from governor.core.catalogue import load_kpis

        _catalogue_count = len(load_kpis(paths.KNOWLEDGE / "kpis.yaml").kpis)
    except Exception:  # noqa: BLE001 — a missing catalogue is an empty funnel, not an error
        _catalogue_count = None
    return _catalogue_count  # type: ignore[return-value]


def _names(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        if isinstance(value, str) and _NAME.fullmatch(value) and value not in out:
            out.append(value)
    return out


def _models(design: dict | None, build: dict | None) -> list[dict]:
    models: list[dict] = []
    seen: set[str] = set()
    for item in (design or {}).get("silver_models") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name) or name in seen:
            continue
        layer = "staging" if item.get("folder") == "staging" else "silver"
        models.append({"name": name, "layer": layer})
        seen.add(name)
    gold = ((build or {}).get("models") or {}).get("gold") if isinstance((build or {}).get("models"), dict) else None
    if not gold and build:
        gold = [item.get("model") for item in build.get("kpis_built") or [] if isinstance(item, dict)]
    for name in _names(gold):
        if name not in seen:
            models.append({"name": name, "layer": "gold"})
            seen.add(name)
    return models


def _known_models(models: list[dict]) -> set[str]:
    return {item["name"] for item in models if item["layer"] in ("staging", "silver")}


def _status(decision: object, gap: object, built_ids: set[str], have_build: bool, kpi_id: str) -> str:
    if decision == "decline":
        if isinstance(gap, dict) and (gap.get("missing") or gap.get("next_step")):
            return "gap"
        return "declined"
    if have_build and kpi_id not in built_ids:
        return "gap"
    return "built"


def _kpis(design: dict | None, build: dict | None, models: list[dict]) -> list[dict]:
    known = _known_models(models)
    built_ids = {
        item["id"] for item in (build or {}).get("kpis_built") or []
        if isinstance(item, dict) and isinstance(item.get("id"), str) and _NAME.fullmatch(item["id"])
    }
    rows: list[dict] = []
    seen: set[str] = set()
    if design and isinstance(design.get("kpis"), list):
        for item in design["kpis"]:
            if not isinstance(item, dict):
                continue
            kpi_id = item.get("id")
            if not isinstance(kpi_id, str) or not _NAME.fullmatch(kpi_id) or kpi_id in seen:
                continue
            seen.add(kpi_id)
            feeding = _names([
                value for value in (item.get("mapping") or {}).values()
                if isinstance(value, str) and value in known
            ]) if isinstance(item.get("mapping"), dict) else []
            rows.append({
                "id": kpi_id,
                "status": _status(item.get("decision"), item.get("gap"), built_ids, build is not None, kpi_id),
                "models": feeding,
            })
    if build:
        for item in build.get("kpis_built") or []:
            if not isinstance(item, dict):
                continue
            kpi_id = item.get("id")
            if not isinstance(kpi_id, str) or not _NAME.fullmatch(kpi_id) or kpi_id in seen:
                continue
            seen.add(kpi_id)
            rows.append({"id": kpi_id, "status": "built", "models": []})
        for item in build.get("gaps") or []:
            if not isinstance(item, dict):
                continue
            kpi_id = item.get("id")
            if not isinstance(kpi_id, str) or not _NAME.fullmatch(kpi_id) or kpi_id in seen:
                continue
            seen.add(kpi_id)
            rows.append({"id": kpi_id, "status": "gap", "models": []})
    return rows


def _findings(build: dict | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not build:
        return counts
    for item in build.get("blueprint") or []:
        if not isinstance(item, dict):
            continue
        code = item.get("code") if isinstance(item.get("code"), str) else item.get("rule")
        if isinstance(code, str) and _CODE.fullmatch(code):
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _tests(build: dict | None) -> int | None:
    if not build or "tests_passed" not in build:
        return None
    value = build["tests_passed"]
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, dict):
        total = _int(value.get("total"))
        if total is not None:
            return total
        parts = [_int(part) for key, part in value.items() if key != "total"]
        numbers = [part for part in parts if part is not None]
        return sum(numbers) if numbers else None
    return None


def _repairs(build: dict | None) -> int | None:
    if not build or "repairs" not in build:
        return None
    return _int(build.get("repairs"))


def _lineage_layer(node: dict) -> str | None:
    if node.get("resource_type") == "source":
        return "raw"
    name = node.get("name") if isinstance(node.get("name"), str) else ""
    fqn = [str(part) for part in node.get("fqn") or []]
    if name.startswith("kpi_") or "kpi" in fqn:
        return "kpi"
    if name.startswith(("stg_", "int_")) or "staging" in fqn or "intermediate" in fqn:
        return "silver"
    if node.get("resource_type") == "model":
        return "gold"
    return None


def _lineage(manifest: dict | None) -> dict:
    if not manifest:
        return {"nodes": [], "edges": []}
    catalog: dict = {}
    for key in ("nodes", "sources"):
        block = manifest.get(key)
        if isinstance(block, dict):
            catalog.update(block)
    drawn: dict[str, dict] = {}
    for uid, node in catalog.items():
        if not isinstance(uid, str) or not isinstance(node, dict):
            continue
        if node.get("resource_type") not in ("model", "source"):
            continue
        name = node.get("name")
        layer = _lineage_layer(node)
        if not isinstance(name, str) or not _NAME.fullmatch(name) or layer not in _LINEAGE_LAYER:
            continue
        drawn[uid] = {"id": name, "layer": layer}
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for uid, node in catalog.items():
        if uid not in drawn or not isinstance(node, dict):
            continue
        depends = node.get("depends_on")
        parents = depends.get("nodes") if isinstance(depends, dict) else None
        if not isinstance(parents, list):
            continue
        for parent in parents:
            if parent not in drawn:
                continue
            pair = (drawn[parent]["id"], drawn[uid]["id"])
            if pair[0] == pair[1] or pair in seen:
                continue
            seen.add(pair)
            edges.append({"source": pair[0], "target": pair[1]})
    nodes = list({item["id"]: item for item in drawn.values()}.values())
    nodes.sort(key=lambda item: (_layer_order(item["layer"]), item["id"]))
    edges.sort(key=lambda item: (item["source"], item["target"]))
    return {"nodes": nodes, "edges": edges}


def _layer_order(layer: str) -> int:
    return {"raw": 0, "silver": 1, "gold": 2, "kpi": 3}.get(layer, 9)


def _funnel(design: dict | None, build: dict | None, kpis: list[dict]) -> dict:
    if design is None:
        proposed = computable = validated = None
    else:
        items = [item for item in design.get("kpis") or [] if isinstance(item, dict) and isinstance(item.get("id"), str)]
        proposed = len(items)
        computable = sum(1 for item in items if item.get("decision") == "build")
        validated = proposed
    built = None if build is None else sum(1 for item in kpis if item["status"] == "built")
    return {
        "requested": _catalogue_size(),
        "computable": computable,
        "proposed": proposed,
        "validated": validated,
        "built": built,
    }


def from_target(folder: Path) -> dict:
    """Read ``governor/build.json``, ``governor/design.json`` and ``target/manifest.json``."""
    build = _load(folder / "governor" / "build.json")
    design = _load(folder / "governor" / "design.json")
    manifest = _load(folder / "target" / "manifest.json")
    if build is None and design is None and manifest is None:
        return empty()
    models = _models(design, build)
    kpis = _kpis(design, build, models)
    payload = empty()
    payload["kpis"] = kpis
    payload["models"] = models
    payload["tests_passed"] = _tests(build)
    payload["repairs"] = _repairs(build)
    payload["finding_codes"] = _findings(build)
    payload["funnel"] = _funnel(design, build, kpis)
    payload["lineage"] = _lineage(manifest)
    return payload


def coerce(data: dict) -> dict:
    """Keep the public shape. Anything else (paths, prose, SQL) is dropped."""
    payload = empty()
    kpis = []
    for item in data.get("kpis") or []:
        if not isinstance(item, dict):
            continue
        kpi_id, status = item.get("id"), item.get("status")
        if not isinstance(kpi_id, str) or not _NAME.fullmatch(kpi_id) or status not in _KPI_STATUS:
            continue
        kpis.append({"id": kpi_id, "status": status, "models": _names(item.get("models"))})
    models = []
    for item in data.get("models") or []:
        if not isinstance(item, dict):
            continue
        name, layer = item.get("name"), item.get("layer")
        if isinstance(name, str) and _NAME.fullmatch(name) and layer in _MODEL_LAYER:
            models.append({"name": name, "layer": layer})
    codes = {}
    raw_codes = data.get("finding_codes")
    if isinstance(raw_codes, dict):
        for code, count in raw_codes.items():
            number = _int(count)
            if isinstance(code, str) and _CODE.fullmatch(code) and number is not None:
                codes[code] = number
    funnel = dict(payload["funnel"])
    raw_funnel = data.get("funnel")
    if isinstance(raw_funnel, dict):
        for key in funnel:
            if raw_funnel.get(key) is None:
                funnel[key] = None
            else:
                number = _int(raw_funnel.get(key))
                if number is not None:
                    funnel[key] = number
    lineage = _lineage_public(data.get("lineage"))
    payload["kpis"] = kpis
    payload["models"] = models
    payload["tests_passed"] = _int(data.get("tests_passed")) if "tests_passed" in data else None
    if data.get("tests_passed") is None:
        payload["tests_passed"] = None
    payload["repairs"] = _int(data.get("repairs")) if data.get("repairs") is not None else None
    payload["finding_codes"] = dict(sorted(codes.items()))
    payload["funnel"] = funnel
    payload["lineage"] = lineage
    return payload


def _lineage_public(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {"nodes": [], "edges": []}
    nodes = []
    seen: set[str] = set()
    for item in raw.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        name, layer = item.get("id"), item.get("layer")
        if not isinstance(name, str) or not _NAME.fullmatch(name) or layer not in _LINEAGE_LAYER or name in seen:
            continue
        seen.add(name)
        nodes.append({"id": name, "layer": layer})
    edges = []
    pairs: set[tuple[str, str]] = set()
    for item in raw.get("edges") or []:
        if not isinstance(item, dict):
            continue
        source, target = item.get("source"), item.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        if source not in seen or target not in seen or source == target:
            continue
        pair = (source, target)
        if pair in pairs:
            continue
        pairs.add(pair)
        edges.append({"source": source, "target": target})
    nodes.sort(key=lambda item: (_layer_order(item["layer"]), item["id"]))
    edges.sort(key=lambda item: (item["source"], item["target"]))
    return {"nodes": nodes, "edges": edges}


def demo_file(run_id: str) -> dict | None:
    from governor.integrations.console.runs import demo_dir

    for path in (
        demo_dir() / "build" / f"{run_id}.artifacts.json",
        demo_dir() / "ask" / f"{run_id}.artifacts.json",
        demo_dir() / f"{run_id}.artifacts.json",
    ):
        data = _load(path)
        if data is not None:
            return coerce(data)
    return None
