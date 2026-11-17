"""CLI (batch2.md section 8; each command prints one JSON line last):

    python -m governor.build init --target <dir> --project-name <name>
    python -m governor.build profile --schema raw [--policy <file>] [--out <file>]
    python -m governor.build run --target <dir> --project-name <name> [--llm fake:<script.json>|openrouter]
                                 [--policy <file>] [--profile <profile.json>] [--force]
                                 (up_to_date when the raw schema has not changed since the last approved build)
    python -m governor.build approve <thread_id> --by <name> [--llm ...]   (builds silver and gold: built | escalated | blueprint_failed)
    python -m governor.build reject <thread_id> --note "<text>" [--llm ...]
    python -m governor.build publish --target <dir> [--open-pr]         (batch2b section 13)
    python -m governor.build certify --target <dir> --by <name>         (after the merge; deploys to analytics)

``--tenant <name>`` on run, approve, reject, publish and certify (batch3.md section 31.3, needs GOVERNOR_TENANTS):
the tenant's knowledge, run state, database and target; it fills ``--target`` and ``--project-name``, and an
explicit ``--target`` that is not the tenant's is refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg

from governor.build.workspace import build_dsn, init_target, write_sources
from governor.core.paths import KNOWLEDGE

if TYPE_CHECKING:
    from governor.core.tenancy import Tenant

DEFAULT_POLICY = KNOWLEDGE / "shop" / "policy.yaml"


def raw_tables() -> dict[str, list[str]]:
    """Tables and columns of schema ``raw``, read as the build login."""
    tables: dict[str, list[str]] = {}
    with psycopg.connect(build_dsn()) as conn:  # build_dsn() carries connect_timeout
        rows = conn.execute(
            "select c.table_name, c.column_name from information_schema.columns c "
            "join information_schema.tables t using (table_schema, table_name) "
            "where c.table_schema = 'raw' and t.table_type = 'BASE TABLE' "
            "order by c.table_name, c.ordinal_position"
        ).fetchall()
    for table, column in rows:
        tables.setdefault(table, []).append(column)
    return tables


def _fail(what: str, e: Exception) -> int:
    """One readable line, never the connection string."""
    first = str(e).splitlines()[0] if str(e) else ""
    print(f"{what}: {type(e).__name__}: {first}", file=sys.stderr)
    return 1


class UsageError(ValueError):
    """A command line that cannot run (``--tenant`` without a registry, a mismatched ``--target``)."""


def _tenant(args: argparse.Namespace) -> Tenant | None:
    """Resolve ``--tenant`` (batch3.md section 31.3) and fill ``--target`` and ``--project-name`` from it.

    An explicit ``--target`` that is not the tenant's is refused. Without ``--tenant``, ``--target`` (and, for
    ``run``, ``--project-name``) are required as before."""
    name = getattr(args, "tenant", None)
    has_target, has_project = hasattr(args, "target"), hasattr(args, "project_name")
    if not name:
        missing = [flag for flag, there, value in (("--target", has_target, getattr(args, "target", None)),
                                                   ("--project-name", has_project, getattr(args, "project_name", None)))
                   if there and not value]
        if missing:
            raise UsageError(f"{args.cmd} needs {' and '.join(missing)} (or --tenant <name>)")
        return None
    from governor.core.tenancy import load_tenants, tenants_path

    path = tenants_path()
    if path is None:
        raise UsageError("--tenant needs GOVERNOR_TENANTS (the tenant registry file)")
    tenants = load_tenants(path)
    tenant = tenants.get(name)
    if tenant is None:
        raise UsageError(f"unknown tenant {name!r} (known: {', '.join(sorted(tenants))})")
    if has_target:
        if args.target is not None and Path(args.target).resolve() != tenant.target:
            raise UsageError(f"--target {args.target} is not the target of tenant {name} ({tenant.target})")
        args.target = tenant.target
    if has_project and not args.project_name:
        args.project_name = tenant.name
    return tenant


def _usage(args: argparse.Namespace) -> tuple[Tenant | None, int | None]:
    """``(tenant, None)``, or ``(None, exit code)`` after printing one line for a usage or registry error."""
    try:
        return _tenant(args), None
    except UsageError as e:
        print(f"usage: {e}", file=sys.stderr)
        return None, 2
    except Exception as e:  # noqa: BLE001 (a registry that does not load)
        return None, _fail("cannot read the tenant registry", e)


def _init(args: argparse.Namespace) -> int:
    try:
        tables = raw_tables()
    except Exception as e:  # noqa: BLE001
        return _fail("cannot read raw", e)
    init_target(args.target, args.project_name)
    write_sources(args.target, tables)
    print(json.dumps({"target": str(args.target), "tables": sorted(tables)}))
    return 0


def _profile(args: argparse.Namespace) -> int:
    from governor.build.profile import load_policy, profile_schema

    try:
        policy = load_policy(args.policy) if args.policy else None
    except Exception as e:  # noqa: BLE001
        return _fail("cannot read policy", e)
    try:
        profile = profile_schema(build_dsn(), args.schema, policy)
    except Exception as e:  # noqa: BLE001
        return _fail(f"cannot profile {args.schema}", e)
    text = json.dumps(profile)
    if args.out is None:
        print(text)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "schema": args.schema, "tables": len(profile["tables"]),
                      "relationships": len(profile["relationships"]), "pii_policy": bool(policy)}))
    return 0


def _run(args: argparse.Namespace) -> int:
    from governor.build import graph
    from governor.build.llm import make_llm

    tenant, code = _usage(args)
    if code is not None:
        return code
    profile = None
    try:
        llm = make_llm(args.llm)
        if args.profile is not None:
            profile = json.loads(args.profile.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return _fail("cannot start the build", e)
    try:
        from governor.build.publish import ensure_on_main

        ensure_on_main(args.target)  # publish branches from main: never build on an earlier build's branch
    except Exception as e:  # noqa: BLE001
        return _fail("cannot start the build", e)
    init_target(args.target, args.project_name)
    try:
        out = graph.start(args.target, args.project_name, llm, policy=args.policy, profile=profile, force=args.force,
                          tenant=tenant)
    except Exception as e:  # noqa: BLE001
        return _fail("build run failed", e)
    print(json.dumps(out))
    return 0


def _resume(args: argparse.Namespace) -> int:
    from governor.build import graph
    from governor.build.llm import make_llm

    tenant, code = _usage(args)
    if code is not None:
        return code
    try:
        llm = make_llm(args.llm)
        if args.cmd == "approve":
            out = graph.approve(args.thread_id, args.by, llm, tenant=tenant)
        else:
            out = graph.reject(args.thread_id, args.note, llm, tenant=tenant)
    except Exception as e:  # noqa: BLE001
        return _fail(f"build {args.cmd} failed", e)
    print(json.dumps(out))
    return 0


def _publish(args: argparse.Namespace) -> int:
    from governor.build.publish import publish

    _, code = _usage(args)
    if code is not None:
        return code
    try:
        out = publish(args.target, open_pr=args.open_pr)
    except Exception as e:  # noqa: BLE001
        return _fail("publish failed", e)
    if out.get("status") == "nothing_to_publish":  # batch3 section 30.3: a plain message, not an error
        print(f"Nothing to publish: {out.get('reason')}.")
        return 0
    print(json.dumps(out))
    return 0 if out.get("status") == "published" else 1


def _certify(args: argparse.Namespace) -> int:
    from governor.build.certify import certify

    tenant, code = _usage(args)
    if code is not None:
        return code
    try:
        out = certify(args.target, args.by, tenant=tenant)
    except Exception as e:  # noqa: BLE001
        return _fail("certify failed", e)
    print(json.dumps(out))
    return 0 if out.get("status") == "certified" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="governor.build")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create the target dbt project and write models/sources.yml")
    p.add_argument("--target", required=True, type=Path)
    p.add_argument("--project-name", required=True)
    p.set_defaults(func=_init)
    p = sub.add_parser("profile", help="profile a raw schema (counts only for PII columns)")
    p.add_argument("--schema", default="raw")
    p.add_argument("--policy", type=Path, help="column -> PII tag file, e.g. knowledge/shop/policy.yaml")
    p.add_argument("--out", type=Path, help="write the profile here and print a one-line summary")
    p.set_defaults(func=_profile)
    llm_help = "openrouter (default) or fake:<script.json>"
    tenant_help = "a tenant of the GOVERNOR_TENANTS registry: its knowledge, state, database and target"
    p = sub.add_parser("run", help="profile raw, propose and validate the design, stop at the design gate")
    p.add_argument("--target", type=Path, help="required unless --tenant")
    p.add_argument("--project-name", help="required unless --tenant (then the tenant name)")
    p.add_argument("--tenant", help=tenant_help)
    p.add_argument("--llm", default="openrouter", help=llm_help)
    p.add_argument("--policy", type=Path, default=DEFAULT_POLICY, help="column -> PII tag file")
    p.add_argument("--profile", type=Path, help="use a saved profile (from profile --out) instead of profiling raw")
    p.add_argument("--force", action="store_true",
                   help="design again even when the raw schema has not changed since the last approved build")
    p.set_defaults(func=_run)
    p = sub.add_parser("approve", help="approve the design of a thread paused at the design gate")
    p.add_argument("thread_id")
    p.add_argument("--by", required=True)
    p.add_argument("--llm", default="openrouter", help=llm_help)
    p.add_argument("--tenant", help=tenant_help)
    p.set_defaults(func=_resume)
    p = sub.add_parser("reject", help="send the design back to the plan model with a note")
    p.add_argument("thread_id")
    p.add_argument("--note", required=True)
    p.add_argument("--llm", default="openrouter", help=llm_help)
    p.add_argument("--tenant", help=tenant_help)
    p.set_defaults(func=_resume)
    p = sub.add_parser("publish", help="commit a built project to a governor/build-* branch, write governor/pr.md, push")
    p.add_argument("--target", type=Path, help="required unless --tenant")
    p.add_argument("--open-pr", action="store_true", help="also run gh pr create")
    p.add_argument("--tenant", help=tenant_help)
    p.set_defaults(func=_publish)
    p = sub.add_parser("certify", help="after the merge: deploy to analytics as governor_deploy and register the KPIs")
    p.add_argument("--target", type=Path, help="required unless --tenant")
    p.add_argument("--by", required=True)
    p.add_argument("--tenant", help=tenant_help)
    p.set_defaults(func=_certify)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
