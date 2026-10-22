"""Build meta.duckdb from a dbt artifacts directory.

``python -m governor.core.harvest <artifacts_dir> [--out <path>]`` writes
``<artifacts_dir>/meta.duckdb``, or ``<path>`` when ``--out`` is given.
Each incident run later gets its own copy, and ``diff_since_green`` compares
checksums between the two.

Graph nodes are sources, models and exposures. Tests live in the ``tests``
table, one row per model they depend on: a relationships test and a singular
test each name two models. Edges are source → model, model → model and
model → exposure.

``results.status`` is copied from ``run_results.json``. A model row is
``success`` and an exposure row is ``no-op``. Test rows use pass, warn,
fail, error or skipped. Severity is set on test rows only.

Freshness timestamps stay the strings from ``sources.json``, so a later
comparison does not shift the timezone. ``warn_after`` and ``error_after``
are stored as ``{count} {period}``, for example ``12 hour``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import yaml

from governor.core import paths

TABLE_NAMES = (
    "nodes",
    "columns",
    "edges",
    "tests",
    "exposures",
    "results",
    "freshness",
)

# Column order is the table contract. "schema" and "column" are quoted
# because they are reserved words in DuckDB.
_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "nodes": [
        ("unique_id", "VARCHAR"),
        ("resource_type", "VARCHAR"),
        ("name", "VARCHAR"),
        ("schema", "VARCHAR"),
        ("path", "VARCHAR"),
        ("owner", "VARCHAR"),
        ("description", "VARCHAR"),
        ("checksum", "VARCHAR"),
        ("tags", "VARCHAR[]"),
    ],
    "columns": [
        ("unique_id", "VARCHAR"),
        ("column", "VARCHAR"),
        ("data_type", "VARCHAR"),
        ("description", "VARCHAR"),
        ("pii_tag", "VARCHAR"),
    ],
    "edges": [
        ("parent", "VARCHAR"),
        ("child", "VARCHAR"),
    ],
    "tests": [
        ("unique_id", "VARCHAR"),
        ("attached_node", "VARCHAR"),
        ("column", "VARCHAR"),
        ("test_type", "VARCHAR"),
        ("severity", "VARCHAR"),
    ],
    "exposures": [
        ("unique_id", "VARCHAR"),
        ("name", "VARCHAR"),
        ("depends_on", "VARCHAR[]"),
    ],
    "results": [
        ("unique_id", "VARCHAR"),
        ("resource_type", "VARCHAR"),
        ("status", "VARCHAR"),
        ("severity", "VARCHAR"),
        ("failures", "BIGINT"),
        ("message", "VARCHAR"),
    ],
    "freshness": [
        ("unique_id", "VARCHAR"),
        ("status", "VARCHAR"),
        ("max_loaded_at", "VARCHAR"),
        ("snapshotted_at", "VARCHAR"),
        ("warn_after", "VARCHAR"),
        ("error_after", "VARCHAR"),
    ],
}

_PRIMARY_KEYS = {
    "nodes": ("unique_id",),
    "columns": ("unique_id", "column"),
    "edges": ("parent", "child"),
    "tests": ("unique_id", "attached_node"),
    "exposures": ("unique_id",),
    "results": ("unique_id",),
    "freshness": ("unique_id",),
}

_ARTIFACTS = ("manifest.json", "catalog.json", "run_results.json", "sources.json")
_META_DB = "meta.duckdb"
_GRAPH_PREFIXES = ("source.", "model.", "exposure.")


class HarvestError(Exception):
    """The artifacts directory cannot be turned into meta.duckdb."""


def load_tables(
    artifacts_dir: str | Path,
    owners_path: str | Path | None = None,
    policy_path: str | Path | None = None,
) -> dict[str, list[dict]]:
    """Read the artifacts and return the seven tables as lists of row dicts.

    Does not write a database. ``harvest`` writes ``meta.duckdb``.
    """
    artifacts_dir = Path(artifacts_dir)
    if not artifacts_dir.is_dir():
        raise HarvestError(f"artifacts directory not found: {artifacts_dir}")

    paths = {name: artifacts_dir / name for name in _ARTIFACTS}
    for path in paths.values():
        if not path.is_file():
            raise HarvestError(f"missing artifact: {path}")

    owners_file, policy_file = _knowledge_paths(owners_path, policy_path)
    owners = _load_yaml_map(owners_file)
    policy = _load_yaml_map(policy_file)

    manifest = _load_json(paths["manifest.json"])
    catalog = _load_json(paths["catalog.json"])
    run_results = _load_json(paths["run_results.json"])
    sources = _load_json(paths["sources.json"])
    _require_manifest(manifest)

    return {
        "nodes": _node_rows(manifest, owners),
        "columns": _column_rows(manifest, catalog, policy),
        "edges": _edge_rows(manifest),
        "tests": _test_rows(manifest),
        "exposures": _exposure_rows(manifest),
        "results": _result_rows(manifest, run_results),
        "freshness": _freshness_rows(sources),
    }


def as_graph(tables: dict[str, list[dict]]) -> dict:
    """The lineage dict for these tables."""
    return {
        "nodes": [row["unique_id"] for row in tables["nodes"]],
        "edges": [
            {"parent": row["parent"], "child": row["child"]} for row in tables["edges"]
        ],
    }


def harvest(
    artifacts_dir: str | Path,
    owners_path: str | Path | None = None,
    policy_path: str | Path | None = None,
    out: str | Path | None = None,
) -> dict[str, int]:
    """Write ``<artifacts_dir>/meta.duckdb`` (or ``out``) and return a row count per table.

    Running it again replaces the seven tables in that file.
    """
    artifacts_dir = Path(artifacts_dir)
    tables = load_tables(artifacts_dir, owners_path, policy_path)
    _write_meta(Path(out) if out is not None else artifacts_dir / _META_DB, tables)
    return {name: len(tables[name]) for name in TABLE_NAMES}


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Prints one ``name count`` line per table."""
    args = list(sys.argv[1:] if argv is None else argv)
    out = None
    if len(args) == 3 and args[1] == "--out":
        out = args[2]
        args = args[:1]
    if len(args) != 1:
        print("usage: python -m governor.core.harvest <artifacts_dir> [--out <path>]", file=sys.stderr)
        return 2
    try:
        counts = harvest(args[0], out=out)
    except HarvestError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for name in TABLE_NAMES:
        print(f"{name} {counts[name]}")
    return 0


def _knowledge_paths(
    owners_path: str | Path | None,
    policy_path: str | Path | None,
) -> tuple[Path, Path]:
    default_owners = paths.KNOWLEDGE / "owners.yaml"
    default_policy = paths.KNOWLEDGE / "policy.yaml"
    return (
        Path(owners_path) if owners_path is not None else default_owners,
        Path(policy_path) if policy_path is not None else default_policy,
    )


def _load_yaml_map(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise HarvestError(f"missing knowledge file: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise HarvestError(f"{path} must be a mapping.")
    return {str(key): str(value) for key, value in loaded.items()}


def _load_json(path: Path) -> dict:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HarvestError(f"could not parse {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise HarvestError(f"{path} must be a JSON object.")
    return loaded


def _require_manifest(manifest: dict) -> None:
    for key in ("nodes", "sources", "exposures"):
        if not isinstance(manifest.get(key), dict):
            raise HarvestError(f"manifest.json is missing '{key}'.")


def _node_rows(manifest: dict, owners: dict[str, str]) -> list[dict]:
    subjects: list[dict] = []
    subjects.extend(manifest["sources"].values())
    subjects.extend(
        node for node in manifest["nodes"].values() if node.get("resource_type") == "model"
    )
    subjects.extend(manifest["exposures"].values())
    rows = [_node_row(node, owners) for node in subjects]
    rows.sort(key=lambda row: row["unique_id"])
    return rows


def _node_row(node: dict, owners: dict[str, str]) -> dict:
    unique_id = node["unique_id"]
    tags = node.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return {
        "unique_id": unique_id,
        "resource_type": node["resource_type"],
        "name": node["name"],
        "schema": node.get("schema"),
        "path": _slash(node.get("original_file_path") or node.get("path")),
        "owner": owners.get(unique_id),
        "description": _text(node.get("description")),
        "checksum": _checksum(node),
        "tags": [str(tag) for tag in tags],
    }


def _column_rows(manifest: dict, catalog: dict, policy: dict[str, str]) -> list[dict]:
    subjects: list[dict] = []
    subjects.extend(manifest["sources"].values())
    subjects.extend(
        node for node in manifest["nodes"].values() if node.get("resource_type") == "model"
    )
    rows: list[dict] = []
    for node in subjects:
        unique_id = node["unique_id"]
        declared = node.get("columns") or {}
        catalog_types = _catalog_types(catalog, unique_id)
        names = set(declared) | set(catalog_types)
        for name in sorted(names):
            column = declared.get(name) or {}
            description = column.get("description") if isinstance(column, dict) else None
            rows.append(
                {
                    "unique_id": unique_id,
                    "column": name,
                    "data_type": catalog_types.get(name),
                    "description": _text(description),
                    "pii_tag": policy.get(name),
                }
            )
    rows.sort(key=lambda row: (row["unique_id"], row["column"]))
    return rows


def _catalog_types(catalog: dict, unique_id: str) -> dict[str, str | None]:
    for section in ("nodes", "sources"):
        node = (catalog.get(section) or {}).get(unique_id)
        if not node:
            continue
        types: dict[str, str | None] = {}
        for name, column in (node.get("columns") or {}).items():
            data_type = column.get("type") if isinstance(column, dict) else None
            types[name] = str(data_type) if data_type else None
        return types
    return {}


def _edge_rows(manifest: dict) -> list[dict]:
    """Source → model, model → model, model → exposure.

    A test depends on models, but that dependency is a check, not a hop
    in the blast radius. Those links stay in the tests table.
    """
    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []

    def add(parent: str, child: str) -> None:
        if not _is_graph_id(parent) or not _is_graph_id(child):
            return
        key = (parent, child)
        if key in seen:
            return
        seen.add(key)
        rows.append({"parent": parent, "child": child})

    for node in manifest["nodes"].values():
        if node.get("resource_type") != "model":
            continue
        for parent in _depends_on(node):
            add(parent, node["unique_id"])
    for exposure in manifest["exposures"].values():
        for parent in _depends_on(exposure):
            add(parent, exposure["unique_id"])
    rows.sort(key=lambda row: (row["parent"], row["child"]))
    return rows


def _test_rows(manifest: dict) -> list[dict]:
    rows: list[dict] = []
    for node in manifest["nodes"].values():
        if node.get("resource_type") != "test":
            continue
        parents = sorted({uid for uid in _depends_on(node) if _is_graph_id(uid)})
        if not parents:
            raise HarvestError(
                f"test {node['unique_id']} does not depend on a model or source."
            )
        metadata = node.get("test_metadata") or {}
        test_type = metadata.get("name") or node["name"]
        severity = str((node.get("config") or {}).get("severity") or "error").lower()
        column = node.get("column_name") or None
        for parent in parents:
            rows.append(
                {
                    "unique_id": node["unique_id"],
                    "attached_node": parent,
                    "column": column,
                    "test_type": test_type,
                    "severity": severity,
                }
            )
    rows.sort(key=lambda row: (row["unique_id"], row["attached_node"]))
    return rows


def _exposure_rows(manifest: dict) -> list[dict]:
    rows: list[dict] = []
    for exposure in manifest["exposures"].values():
        depends = sorted({uid for uid in _depends_on(exposure) if _is_graph_id(uid)})
        rows.append(
            {
                "unique_id": exposure["unique_id"],
                "name": exposure["name"],
                "depends_on": depends,
            }
        )
    rows.sort(key=lambda row: row["unique_id"])
    return rows


def _result_rows(manifest: dict, run_results: dict) -> list[dict]:
    severity_by_id: dict[str, str] = {}
    for node in manifest["nodes"].values():
        if node.get("resource_type") != "test":
            continue
        severity = str((node.get("config") or {}).get("severity") or "error").lower()
        severity_by_id[node["unique_id"]] = severity

    rows: list[dict] = []
    for result in run_results.get("results") or []:
        unique_id = result["unique_id"]
        message = result.get("message")
        rows.append(
            {
                "unique_id": unique_id,
                "resource_type": _resource_type(manifest, unique_id),
                "status": str(result.get("status") or ""),
                "severity": severity_by_id.get(unique_id),
                "failures": _failures(result.get("failures")),
                "message": None if message is None else str(message),
            }
        )
    return rows


def _freshness_rows(sources: dict) -> list[dict]:
    rows: list[dict] = []
    for result in sources.get("results") or []:
        criteria = result.get("criteria") or {}
        rows.append(
            {
                "unique_id": result["unique_id"],
                "status": str(result.get("status") or ""),
                "max_loaded_at": _optional_str(result.get("max_loaded_at")),
                "snapshotted_at": _optional_str(result.get("snapshotted_at")),
                "warn_after": _window(criteria.get("warn_after")),
                "error_after": _window(criteria.get("error_after")),
            }
        )
    rows.sort(key=lambda row: row["unique_id"])
    return rows


def _resource_type(manifest: dict, unique_id: str) -> str:
    node = manifest["nodes"].get(unique_id)
    if node is not None:
        return str(node.get("resource_type") or "unknown")
    if unique_id in manifest["exposures"]:
        return "exposure"
    if unique_id in manifest["sources"]:
        return "source"
    prefix, _sep, _rest = unique_id.partition(".")
    return prefix or "unknown"


def _depends_on(node: dict) -> list[str]:
    depends = node.get("depends_on") or {}
    nodes = depends.get("nodes") or []
    return [unique_id for unique_id in nodes if isinstance(unique_id, str)]


def _is_graph_id(unique_id: str) -> bool:
    return unique_id.startswith(_GRAPH_PREFIXES)


def _checksum(node: dict) -> str | None:
    checksum = node.get("checksum")
    if not isinstance(checksum, dict):
        return None
    value = checksum.get("checksum")
    if not value:
        return None
    return str(value)


def _slash(path: object) -> str | None:
    if not isinstance(path, str) or not path:
        return None
    return path.replace("\\", "/")


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _failures(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HarvestError(f"failures must be a number; got {value!r}.")
    return int(value)


def _window(window: object) -> str | None:
    if not isinstance(window, dict):
        return None
    count = window.get("count")
    period = window.get("period")
    if count is None or not period:
        return None
    return f"{count} {period}"


def _write_meta(path: Path, tables: dict[str, list[dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    try:
        for name in TABLE_NAMES:
            _replace_table(connection, name, tables[name])
        connection.execute("CHECKPOINT")
    finally:
        connection.close()


def _replace_table(connection: duckdb.DuckDBPyConnection, name: str, rows: list[dict]) -> None:
    columns = _COLUMNS[name]
    quoted_columns = ", ".join(f"{_quote(column)} {kind}" for column, kind in columns)
    quoted_key = ", ".join(_quote(column) for column in _PRIMARY_KEYS[name])
    connection.execute(f"DROP TABLE IF EXISTS {_quote(name)}")
    connection.execute(
        f"CREATE TABLE {_quote(name)} ({quoted_columns}, PRIMARY KEY ({quoted_key}))"
    )
    if not rows:
        return
    names = ", ".join(_quote(column) for column, _kind in columns)
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO {_quote(name)} ({names}) VALUES ({placeholders})"
    for row in rows:
        connection.execute(sql, [row[column] for column, _kind in columns])


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
