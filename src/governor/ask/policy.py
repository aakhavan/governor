"""Role policy for governor-ask, read from human-owned files.

``knowledge/access.yaml`` holds the allowlist, row limits, mask value and the
roles. PII tags come from the metadata store (``meta.duckdb`` ``columns.pii_tag``),
which takes them from ``knowledge/policy.yaml``. Nothing here restates a policy
value: models, columns, limits and the mask are all read from those files.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import duckdb
import yaml

from governor.core import paths

ACCESS_PATH = paths.KNOWLEDGE / "access.yaml"

PII_MODES = ("aggregate_only", "mask")


class UnknownRoleError(KeyError):
    """The role is not defined in access.yaml."""


@dataclass(frozen=True)
class Policy:
    """What one role may query. Table and column names are lower case."""

    role: str
    pii_mode: str
    grants: frozenset[tuple[str, str]]
    models: tuple[str, ...]
    schema: dict[str, dict[str, str]]  # model -> column -> data type
    pii: dict[str, dict[str, str]]  # model -> PII column -> tag
    default_limit: int
    row_cap: int
    timeout_s: float
    mask_value: str

    @classmethod
    def for_role(
        cls,
        role: str,
        access_path: Path | None = None,
        meta_path: Path | None = None,
    ) -> Policy:
        """The policy for ``role``. Raises UnknownRoleError for a role not in access.yaml."""
        access_path = Path(access_path or ACCESS_PATH)
        meta_path = Path(meta_path or paths.META)
        access, schema, pii = _load(
            str(access_path.resolve()),
            _mtime(access_path),
            str(meta_path.resolve()),
            _mtime(meta_path),
        )
        roles = access.get("roles") or {}
        if not isinstance(role, str) or role not in roles:
            raise UnknownRoleError(f"unknown role: {role!r}")
        spec = roles[role] or {}
        mode = spec.get("pii")
        if mode not in PII_MODES:
            raise ValueError(f"role {role!r}: pii must be one of {PII_MODES}, got {mode!r}")
        grants = set()
        for grant in spec.get("grants") or []:
            table, _, column = str(grant).lower().partition(".")
            if not column:
                raise ValueError(f"role {role!r}: grant {grant!r} is not model.column")
            grants.add((table, column))
        limits = access["limits"]
        return cls(
            role=role,
            pii_mode=mode,
            grants=frozenset(grants),
            models=tuple(schema),
            schema=schema,
            pii=pii,
            default_limit=int(limits["default_limit"]),
            row_cap=int(limits["row_cap"]),
            timeout_s=float(limits["timeout_s"]),
            mask_value=str(access["mask_value"]),
        )

    def is_pii(self, table: str, column: str) -> bool:
        return column.lower() in self.pii.get(table.lower(), {})

    def is_hidden(self, table: str, column: str) -> bool:
        """PII this role may not see as a value (not granted)."""
        return self.is_pii(table, column) and (table.lower(), column.lower()) not in self.grants


def roles(access_path: Path | None = None) -> list[str]:
    access_path = Path(access_path or ACCESS_PATH)
    access = yaml.safe_load(access_path.read_text(encoding="utf-8"))
    return list((access.get("roles") or {}).keys())


def _mtime(path: Path) -> float:
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing")
    return path.stat().st_mtime


@lru_cache(maxsize=8)
def _load(access_path: str, _access_mtime: float, meta_path: str, _meta_mtime: float):
    access = yaml.safe_load(Path(access_path).read_text(encoding="utf-8"))
    models = [str(m).lower() for m in access["allowlist"]["models"]]
    connection = duckdb.connect(meta_path, read_only=True)
    try:
        rows = connection.execute(
            """
            SELECT lower(n.name), lower(c."column"), c.data_type, c.pii_tag
            FROM columns c JOIN nodes n ON n.unique_id = c.unique_id
            WHERE n.resource_type = 'model'
            """
        ).fetchall()
    finally:
        connection.close()
    schema: dict[str, dict[str, str]] = {m: {} for m in models}
    pii: dict[str, dict[str, str]] = {m: {} for m in models}
    for table, column, data_type, tag in rows:
        if table in schema:
            schema[table][column] = data_type or "VARCHAR"
            if tag:
                pii[table][column] = tag
    missing = [m for m in models if not schema[m]]
    if missing:
        raise ValueError(f"allowlisted models without columns in meta.duckdb: {missing}")
    return access, schema, pii
