"""governor-ask's read-only tools over MCP (stdio), for Claude Desktop or Cursor.

A thin wrapper over ``governor.ask.service``: five tools, no writes, no
natural-language-to-SQL. The role is fixed for the whole process from
``GOVERNOR_MCP_ROLE`` (default ``analyst``) and checked against access.yaml
at start-up; no tool takes a role, so a client cannot raise its permissions.
Queries go through the validator and the read-only executor.

    uv run python -m governor.ask.mcp_server

Built on the official ``mcp`` SDK 1.x (``FastMCP``); 2.x renamed it and the tool fields.
Stdout carries the protocol; errors go to stderr.
"""

from __future__ import annotations

import os
import sys
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from governor.ask import service
from governor.ask.policy import roles

DEFAULT_ROLE = "analyst"
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def server_role() -> str:
    """The role this process serves, from ``GOVERNOR_MCP_ROLE``; it must exist in access.yaml."""
    role = os.environ.get("GOVERNOR_MCP_ROLE", "").strip() or DEFAULT_ROLE
    if role not in roles():
        raise SystemExit(f"GOVERNOR_MCP_ROLE={role!r} is not a role in access.yaml")
    return role


def build_server(role: str) -> FastMCP:
    """An MCP server whose tools all run as ``role``."""
    mcp = FastMCP(
        name="governor-ask",
        instructions=(
            "Read-only tools over the governed billing warehouse: search the catalog, describe a model, "
            "walk lineage, validate SQL and run a governed SELECT. The role is fixed by the server."
        ),
    )

    @mcp.tool(annotations=READ_ONLY)
    def search_catalog(query: str, k: int = 5) -> dict:
        """Find the catalog and metric cards that best match a query (BM25). Returns card ids, kinds, names and tables."""
        return service.search_catalog(query, k)

    @mcp.tool(annotations=READ_ONLY)
    def describe_model(name: str) -> dict:
        """Describe a queryable model: description, owner, grain, columns with type and PII tag, and tests."""
        return service.describe_model(name, role)

    @mcp.tool(annotations=READ_ONLY)
    def get_lineage(name: str, direction: Literal["upstream", "downstream"] = "upstream", depth: int = 2) -> dict:
        """Upstream or downstream nodes of a queryable model, at most 3 hops."""
        return service.get_lineage(name, role, direction, depth)

    @mcp.tool(annotations=READ_ONLY)
    def validate_sql(sql: str) -> dict:
        """Check a DuckDB SELECT against the governance policy without running it. Returns ok, codes, reasons and the rewritten SQL."""
        return service.validate_sql(sql, role)

    @mcp.tool(annotations=READ_ONLY)
    def run_governed_query(sql: str) -> dict:
        """Validate and run a DuckDB SELECT read-only, with the policy's limits. Returns ok, codes, reasons, columns, rows and row_count."""
        return service.run_query(sql, role)

    return mcp


def main() -> int:
    try:
        role = server_role()
    except SystemExit as error:
        print(error, file=sys.stderr)
        return 2
    build_server(role).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
