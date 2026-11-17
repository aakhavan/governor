"""Certify a merged build: deploy to ``analytics`` and register the KPIs (batch2b section 13).

``certify(target, by)`` is a human command, run after the reviewer merged the pull request:

1. refuses (``not_merged``) unless the published commit (recorded by ``publish``) is an ancestor of ``main``, the
   working tree is on ``main`` and clean;
2. runs ``dbt build --target prod`` as ``governor_deploy`` (schema ``analytics``);
3. as the admin (``GOVERNOR_PG_ADMIN_DSN``) creates ``analytics.governor_certified`` and ``analytics.governor_gaps``
   when missing and resolves the salt;
4. runs the serving apply for ``analytics`` with the shop policy and access files;
5. only then replaces the rows of both registry tables in one transaction, so a serving failure never leaves
   newly certified rows without views.

Registry values come from the merged files (the ``meta`` of ``models/marts/*/_*.yml``, ``governor/build.json``) and
the catalogue (label, grain). ``value_columns`` are the numeric columns of the deployed KPI table other than the
grain column and ``months_since_first``.

The salt for the serving views: ``GOVERNOR_PII_SALT`` when set, else the one already stored in
``private.pii_salt``, else a new random one. The value is never printed.
"""

from __future__ import annotations

import datetime as dt
import os
import secrets
import time
from pathlib import Path
from typing import Any, Callable

import psycopg
from psycopg import sql

from governor.build import publish as pub
from governor.build.dbt import DbtResult, run_dbt
from governor.build.events import emit
from governor.build.workspace import deploy_env
from governor.core import paths
from governor.core.catalogue import load_kpis
from governor.core.pgconn import with_timeout

SCHEMA = "analytics"
DEFAULT_KPIS = paths.KNOWLEDGE / "kpis.yaml"
DEFAULT_POLICY = paths.KNOWLEDGE / "shop" / "policy.yaml"
DEFAULT_ACCESS = paths.KNOWLEDGE / "shop" / "access.yaml"
GRAIN_COLUMN = {"month": "month", "cohort_month": "cohort_month"}
NOT_VALUES = {"months_since_first"}
NUMERIC = {"smallint", "integer", "bigint", "numeric", "real", "double precision", "decimal"}

CERTIFIED_DDL = """
CREATE TABLE {} (
    kpi_id text PRIMARY KEY, model text NOT NULL, label text, definition text, grain text,
    value_columns text[] NOT NULL, owner text, source_tier text, source_ref text,
    template_sha256 text, rendered_sha256 text, certified_by text NOT NULL, certified_at timestamptz NOT NULL,
    git_commit text NOT NULL)
"""
GAPS_DDL = """
CREATE TABLE {} (kpi_id text PRIMARY KEY, missing text[] NOT NULL, typical_sources text[] NOT NULL, next_step text)
"""


class CertifyError(RuntimeError):
    """A deploy step failed; the message is one readable line, never a DSN."""


# --------------------------------------------------------------------------- the merge check


def merge_check(target: Path) -> tuple[str | None, str | None]:
    """``(commit, None)`` when the published commit is in ``main`` and the tree is clean on ``main``;
    ``(commit or None, reason)`` otherwise."""
    if not (target / ".git").exists():
        return None, "the target is not a git repository; run publish first"
    rec = pub.read_published(target)
    if not rec or not rec.get("commit"):
        return None, "no published commit recorded; run publish first"
    commit = str(rec["commit"])
    head = pub.git(target, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
    if head != pub.MAIN:
        return commit, f"the working tree is on {head or 'a detached HEAD'!r}, not main"
    if pub.git(target, "status", "--porcelain").stdout.strip():
        return commit, "the working tree on main has uncommitted changes"
    if pub.git(target, "merge-base", "--is-ancestor", commit, pub.MAIN, check=False).returncode != 0:
        return commit, f"the published commit {commit[:12]} is not merged into main"
    return commit, None


# --------------------------------------------------------------------------- database


def _admin_dsn() -> str:
    dsn = os.environ.get("GOVERNOR_PG_ADMIN_DSN")
    if not dsn:
        raise CertifyError("set GOVERNOR_PG_ADMIN_DSN")
    return dsn


def _value_columns(conn: psycopg.Connection, model: str, grain: str | None) -> list[str]:
    rows = conn.execute(
        "select column_name, data_type from information_schema.columns where table_schema = %s and table_name = %s "
        "order by ordinal_position", [SCHEMA, model]).fetchall()
    if not rows:
        raise CertifyError(f"{SCHEMA}.{model} was not deployed")
    skip = NOT_VALUES | ({GRAIN_COLUMN[grain]} if grain in GRAIN_COLUMN else set())
    return [c for c, t in rows if c not in skip and t in NUMERIC]


def registry_rows(target: Path, build: dict, conn: psycopg.Connection, *, by: str, commit: str,
                  certified_at: dt.datetime, kpis_path: Path = DEFAULT_KPIS) -> tuple[list[dict], list[dict]]:
    catalogue = load_kpis(kpis_path)
    meta = pub.kpi_meta(target)
    certified = []
    for k in build.get("kpis_built") or []:
        kid = str(k["id"])
        m = meta.get(kid)
        if m is None:
            raise CertifyError(f"no model yml meta for KPI {kid} in models/marts")
        kpi = catalogue.get(kid)
        model = str(m.get("model") or k.get("model"))
        certified.append({
            "kpi_id": kid, "model": model, "label": kpi.label, "definition": " ".join(kpi.definition.split()),
            "grain": kpi.grain, "value_columns": _value_columns(conn, model, kpi.grain),
            "owner": m.get("owner") or kpi.owner, "source_tier": m.get("source_tier"),
            "source_ref": m.get("source_ref"), "template_sha256": m.get("template_sha256"),
            "rendered_sha256": m.get("rendered_sha256"), "certified_by": by, "certified_at": certified_at,
            "git_commit": commit})
    gaps = [{"kpi_id": str(g["id"]), "missing": list(g.get("missing") or []),
             "typical_sources": list(g.get("typical_sources") or []), "next_step": g.get("next_step") or ""}
            for g in build.get("gaps") or []]
    return certified, gaps


def _ensure(conn: psycopg.Connection, table: str, ddl: str) -> None:
    """Create the registry table when missing (never dropped: the serving views depend on it)."""
    ident = sql.Identifier(SCHEMA, table)
    conn.execute(sql.SQL(ddl.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)).format(ident))
    conn.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM PUBLIC").format(ident))


def _fill(conn: psycopg.Connection, table: str, rows: list[dict]) -> None:
    ident = sql.Identifier(SCHEMA, table)
    conn.execute(sql.SQL("DELETE FROM {}").format(ident))
    if not rows:
        return
    cols = list(rows[0])
    stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        ident, sql.SQL(", ").join(map(sql.Identifier, cols)), sql.SQL(", ").join(sql.Placeholder() * len(cols)))
    with conn.cursor() as cur:
        cur.executemany(stmt, [[r[c] for c in cols] for r in rows])


def _salt(conn: psycopg.Connection) -> tuple[str, str]:
    env = os.environ.get("GOVERNOR_PII_SALT")
    if env:
        return env, "env"
    exists = conn.execute("select to_regclass('private.pii_salt')").fetchone()[0]
    if exists:
        row = conn.execute("select salt from private.pii_salt limit 1").fetchone()
        if row and row[0]:
            return str(row[0]), "stored"
    return secrets.token_hex(16), "generated"


def prepare_registry(dsn: str) -> str:
    """Create both registry tables when missing (so the serving views cover them) and resolve the salt.
    Returns where the salt came from; the salt itself goes to this process's environment only."""
    with psycopg.connect(with_timeout(dsn), autocommit=False) as conn:
        _ensure(conn, "governor_certified", CERTIFIED_DDL)
        _ensure(conn, "governor_gaps", GAPS_DDL)
        salt, salt_from = _salt(conn)
        conn.commit()
    os.environ.setdefault("GOVERNOR_PII_SALT", salt)
    return salt_from


def write_registry(target: Path, build: dict, *, by: str, commit: str, dsn: str) -> tuple[list[dict], list[dict]]:
    """Replace the rows of both registry tables in one transaction (after the serving views exist)."""
    with psycopg.connect(with_timeout(dsn), autocommit=False) as conn:
        certified, gaps = registry_rows(target, build, conn, by=by, commit=commit,
                                        certified_at=dt.datetime.now(dt.timezone.utc))
        _fill(conn, "governor_certified", certified)
        _fill(conn, "governor_gaps", gaps)
        conn.commit()
    return certified, gaps


def serve(dsn: str, policy: Path = DEFAULT_POLICY, access: Path = DEFAULT_ACCESS) -> dict:
    from governor.core import serving

    return serving.apply(SCHEMA, serving.load_policy(policy, access), dsn=dsn, salt=os.environ["GOVERNOR_PII_SALT"])


# --------------------------------------------------------------------------- certify


def _dbt_failures(res: DbtResult) -> list[str]:
    return [f"{r.get('unique_id')} {r.get('status')}" for r in res.results
            if (r.get("status") or "").lower() in ("error", "fail", "runtime error")]


def certify(target: str | Path, by: str, *, dbt_runner: Callable[..., DbtResult] = run_dbt) -> dict:
    started = time.monotonic()
    target = Path(target).resolve()
    by = (by or "").strip()
    if not by:
        raise CertifyError("certify needs --by <name>")
    if os.environ.get("GOVERNOR_PII_SALT") == "":
        raise CertifyError("GOVERNOR_PII_SALT is set but empty; unset it or give it a value")
    commit, reason = merge_check(target)
    if reason:
        return {"status": "not_merged", "reason": reason, "commit": commit}
    build = pub.load_build(target)
    if not build or build.get("status") != "built":
        return {"status": "not_built", "reason": f"governor/build.json on main says {(build or {}).get('status')!r}"}

    dsn = _admin_dsn()
    res = dbt_runner(target, ["build", "--target", "prod"], timeout_s=2400, env=deploy_env())
    failures = _dbt_failures(res)
    if not res.ok or failures or not res.results:
        tail = "; ".join(failures[:5]) or (res.log_tail.strip().splitlines() or ["no results"])[-1]
        return {"status": "deploy_failed", "reason": f"dbt build --target prod failed: {tail[:500]}", "commit": commit}
    tests = sum(1 for r in res.results if str(r.get("unique_id") or "").startswith("test.")
                and (r.get("status") or "").lower() == "pass")

    salt_from = prepare_registry(dsn)
    served = serve(dsn)  # a serving failure raises here, before any certified row is written
    certified, gaps = write_registry(target, build, by=by, commit=commit, dsn=dsn)
    kpis = [c["kpi_id"] for c in certified]
    emit("certified", thread_id=build.get("thread_id"), by=by, commit=commit, kpis=kpis,
         gaps=[g["kpi_id"] for g in gaps], tests_passed=tests, views=served.get("views"),
         seconds=round(time.monotonic() - started, 1))
    out: dict[str, Any] = {"status": "certified", "kpis": kpis, "commit": commit, "gaps": [g["kpi_id"] for g in gaps],
                           "tests_passed": tests, "serving_views": served.get("views"), "salt": salt_from}
    return out


__all__ = ["CertifyError", "certify", "merge_check", "registry_rows"]
