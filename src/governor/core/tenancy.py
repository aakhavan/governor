"""Tenants: one registry file, each tenant a root folder, a target repository and a database (batch3.md section 31).

A tenant's knowledge and run state live under its ``root``; its build connects to its own database. Code passes the
:class:`Tenant` explicitly; nothing here changes module-level paths or ``os.environ``. Without a registry
(``GOVERNOR_TENANTS`` unset) governor runs single-tenant as before.

Registry format::

    tenants:
      acme:   {root: tenants/acme, target: ../acme-dbt, pg_port: 55432}
      globex: {root: tenants/globex, target: ../globex-dbt, pg_port: 55433, pg_host: localhost, pg_db: shop}

Relative paths resolve against the registry file's folder.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from psycopg.conninfo import make_conninfo

from governor.core.pgconn import with_timeout

ENV_TENANTS = "GOVERNOR_TENANTS"
NAME = re.compile(r"[A-Za-z0-9_-]+")
REQUIRED = ("root", "target", "pg_port")
KEYS = frozenset(REQUIRED) | {"pg_host", "pg_db"}
CHECKPOINT_FILE = "build_checkpoints.sqlite"  # the same file name as governor.build.graph.CHECKPOINT_FILE


class TenantError(ValueError):
    """A registry that cannot be used; the message names the tenant and the problem."""


@dataclass(frozen=True, kw_only=True)
class Tenant:
    name: str
    root: Path
    target: Path
    pg_port: int
    pg_host: str = "localhost"
    pg_db: str = "shop"

    # ------------------------------------------------------------------ derived paths

    @property
    def knowledge(self) -> Path:
        return self.root / "knowledge"

    @property
    def kpis_path(self) -> Path:
        return self.knowledge / "kpis.yaml"

    @property
    def blueprint_path(self) -> Path:
        return self.knowledge / "blueprint.md"

    @property
    def approved_default(self) -> Path:
        return self.knowledge / "approved.yaml"

    @property
    def policy_path(self) -> Path:
        return self.knowledge / "shop" / "policy.yaml"

    @property
    def access_path(self) -> Path:
        return self.knowledge / "shop" / "access.yaml"

    @property
    def state_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def checkpoints(self) -> Path:
        return self.state_dir / CHECKPOINT_FILE

    # ------------------------------------------------------------------ database

    @property
    def address(self) -> str:
        """``host:port/db`` for messages: never a user, password or full DSN."""
        return f"{self.pg_host}:{self.pg_port}/{self.pg_db}"

    def build_dsn(self) -> str:
        """The build login (from env, test-bed defaults as in ``workspace.build_dsn``) on this tenant's database."""
        return with_timeout(make_conninfo(
            host=self.pg_host,
            port=str(self.pg_port),
            dbname=self.pg_db,
            user=os.environ.get("GOVERNOR_BUILD_USER") or "governor_build",
            password=os.environ.get("GOVERNOR_BUILD_PASSWORD") or "governor_build_local",
        ))

    def dbt_env(self, base: Mapping[str, str] | None = None) -> dict[str, str]:
        """The caller's environment (``base``, default ``os.environ``) with this tenant's database for dbt."""
        env = dict(os.environ if base is None else base)
        env.update(GOVERNOR_PG_HOST=self.pg_host, GOVERNOR_PG_PORT=str(self.pg_port), GOVERNOR_PG_DB=self.pg_db)
        return env


# --------------------------------------------------------------------------- registry


def dbt_project_name(tenant: str) -> str:
    """dbt project names allow letters, digits and ``_`` and start with a letter or ``_``: ``-`` becomes ``_``."""
    name = tenant.replace("-", "_")
    return name if not name[:1].isdigit() else f"t_{name}"


def tenants_path() -> Path | None:
    """The registry file from ``GOVERNOR_TENANTS``; ``None`` (single-tenant) when unset or empty."""
    raw = (os.environ.get(ENV_TENANTS) or "").strip()
    return Path(raw) if raw else None


def _tenant(name: Any, entry: Any, base: Path) -> Tenant:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise TenantError(f"tenant {name!r}: bad name (use letters, digits, '_' and '-')")
    if not isinstance(entry, dict):
        raise TenantError(f"tenant {name}: expected a mapping with {', '.join(REQUIRED)}")
    unknown = sorted(set(map(str, entry)) - KEYS)
    if unknown:
        raise TenantError(f"tenant {name}: unknown key {', '.join(unknown)} (allowed: {', '.join(sorted(KEYS))})")
    missing = [k for k in REQUIRED if entry.get(k) in (None, "")]
    if missing:
        raise TenantError(f"tenant {name}: missing {', '.join(missing)}")
    port = entry["pg_port"]
    if isinstance(port, bool) or not str(port).strip().isdigit():
        raise TenantError(f"tenant {name}: pg_port must be a port number, got {port!r}")
    for key in ("pg_host", "pg_db"):
        if key in entry and (not isinstance(entry[key], str) or not entry[key].strip()):
            raise TenantError(f"tenant {name}: {key} must be a non-empty string")
    tenant = Tenant(name=name, root=(base / str(entry["root"])).resolve(), target=(base / str(entry["target"])).resolve(),
                    pg_port=int(str(port).strip()), pg_host=str(entry.get("pg_host") or "localhost").strip(),
                    pg_db=str(entry.get("pg_db") or "shop").strip())
    for path in (tenant.kpis_path, tenant.blueprint_path):
        if not path.is_file():
            raise TenantError(f"tenant {name}: missing knowledge/{path.name} under {tenant.root}")
    return tenant


def load_tenants(path: str | Path) -> dict[str, Tenant]:
    """Read and check a registry file. Relative ``root`` and ``target`` resolve against the file's folder."""
    path = Path(path)
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TenantError(f"cannot read the tenant registry {path}: {type(exc).__name__}") from None
    except yaml.YAMLError as exc:
        raise TenantError(f"the tenant registry {path} is not valid YAML ({exc})") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("tenants"), dict) or not doc["tenants"]:
        raise TenantError(f"the tenant registry {path} needs a 'tenants:' mapping with at least one tenant")
    extra = sorted(set(map(str, doc)) - {"tenants"})
    if extra:
        raise TenantError(f"the tenant registry {path}: unknown key {', '.join(extra)}")
    base = path.resolve().parent
    out: dict[str, Tenant] = {}
    seen: dict[str, dict[Any, str]] = {"root": {}, "target": {}, "database": {}}
    for name, entry in doc["tenants"].items():
        tenant = _tenant(name, entry, base)
        for what, key in (("root", os.path.normcase(str(tenant.root))), ("target", os.path.normcase(str(tenant.target))),
                          ("database", (tenant.pg_host.lower(), tenant.pg_port, tenant.pg_db))):
            other = seen[what].get(key)
            if other is not None:
                shown = tenant.address if what == "database" else str(getattr(tenant, what))
                raise TenantError(f"tenant {name}: shares its {what} ({shown}) with tenant {other}")
            seen[what][key] = name
        out[name] = tenant
    return out


__all__ = ["ENV_TENANTS", "Tenant", "TenantError", "dbt_project_name", "load_tenants", "tenants_path"]
