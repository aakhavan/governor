"""Upstream and downstream closures over a plain graph dict.

The graph is ``{"nodes": [unique_id, ...], "edges": [{"parent", "child"}, ...]}``.
Nodes are source, model and exposure ids. Tests are not part of this graph.

Closures exclude the start node. ``depth`` is a hop limit. Results are in
topological order. When several nodes are ready, the alphabetically first
unique id is next, so the order does not depend on dict or file order.

``root_failures`` is what ``load_incident`` will call in P5. A failing node
is a root when no upstream node is also failing. The direct parent is not
enough: a staging model and its mart can both fail with a healthy model
between them, and the staging model is still the root.

``failing_nodes`` turns run results into those graph ids. Tests are not
nodes. An error-severity test is charged to the most downstream model it
reads, a model error to that model, and a freshness error to that source.
Warn results stay out: they are evidence, not the first break.
"""

from __future__ import annotations

from collections import defaultdict


def upstream(unique_id: str, graph: dict, depth: int) -> list[str]:
    """Ancestors at most ``depth`` hops away, in topological order."""
    return _closure(unique_id, graph, depth, direction="upstream")


def downstream(unique_id: str, graph: dict, depth: int) -> list[str]:
    """Descendants at most ``depth`` hops away, in topological order."""
    return _closure(unique_id, graph, depth, direction="downstream")


def descendants(unique_id: str, graph: dict) -> list[str]:
    """Every node reachable downstream, including exposures.

    There is no depth limit. Exposures are included when an edge points at
    them. The start node is not included.
    """
    nodes, parents, children = _adjacency(graph)
    found = _within(unique_id, children, depth=_hop_ceiling(nodes))
    order = _topological_order(nodes, parents, children)
    return [node for node in order if node in found]


def topological_order(graph: dict) -> list[str]:
    """Every graph node, parents before children."""
    nodes, parents, children = _adjacency(graph)
    return _topological_order(nodes, parents, children)


def root_failures(failing_ids: list[str], graph: dict) -> list[str]:
    """Failing nodes with no failing ancestor, in topological order.

    Ids that are not in the graph have no ancestor here, so they are kept
    and listed after the graph nodes, sorted alphabetically. Duplicate ids
    are ignored. An empty input returns an empty list.
    """
    failing: list[str] = []
    seen: set[str] = set()
    for unique_id in failing_ids:
        if unique_id in seen:
            continue
        seen.add(unique_id)
        failing.append(unique_id)

    nodes, parents, children = _adjacency(graph)
    order = _topological_order(nodes, parents, children)
    position = {unique_id: index for index, unique_id in enumerate(order)}

    roots: list[str] = []
    unknown: list[str] = []
    for unique_id in failing:
        if unique_id not in nodes:
            unknown.append(unique_id)
            continue
        ancestors = _ancestors(unique_id, parents)
        if ancestors.isdisjoint(seen):
            roots.append(unique_id)
    roots.sort(key=lambda unique_id: position[unique_id])
    unknown.sort()
    return roots + unknown


def failing_nodes(
    results: list[dict],
    tests: list[dict],
    graph: dict,
    freshness: list[dict] | None = None,
) -> list[str]:
    """Graph nodes that failed at error level, in the order they were found.

    ``results`` rows need ``unique_id``, ``resource_type``, ``status`` and,
    for a test, ``severity``. ``tests`` rows need ``unique_id`` and
    ``attached_node`` (one row per model the test depends on). A row may set
    ``primary`` when that model is the one dbt attached the test to.

    Duplicate ids are kept. ``root_failures`` drops them. An error-severity
    test with no attached model raises ``ValueError``: there is nothing to
    charge the failure to.
    """
    attached: dict[str, list[str]] = defaultdict(list)
    primary: dict[str, str] = {}
    for row in tests:
        attached[row["unique_id"]].append(row["attached_node"])
        if row.get("primary"):
            primary[row["unique_id"]] = row["attached_node"]

    found: list[str] = []
    for row in results:
        status = str(row.get("status") or "").lower()
        resource_type = str(row.get("resource_type") or "")
        unique_id = row["unique_id"]
        if resource_type == "model" and status == "error":
            found.append(unique_id)
            continue
        if resource_type != "test":
            continue
        severity = str(row.get("severity") or "").lower()
        if severity != "error" or status not in {"fail", "error"}:
            continue
        models = attached.get(unique_id) or []
        if not models:
            raise ValueError(
                f"error-severity test {unique_id} does not depend on a model."
            )
        found.append(_most_downstream(models, graph, primary.get(unique_id)))

    for row in freshness or []:
        if str(row.get("status") or "").lower() == "error":
            found.append(row["unique_id"])
    return found


def failing_checks(
    results: list[dict],
    tests: list[dict],
    graph: dict,
    freshness: list[dict] | None = None,
) -> list[dict]:
    """Error-level checks and the graph node each one is charged to.

    Same rules as ``failing_nodes``. The check id is kept so a later run can
    be asked whether that same check already failed. Duplicate charges are
    kept; ``root_failures`` is what drops a downstream node.

    Each dict has ``check_id``, ``kind`` (``model``, ``test`` or
    ``freshness``), ``status``, ``node`` and ``severity``.
    """
    attached: dict[str, list[str]] = defaultdict(list)
    primary: dict[str, str] = {}
    for row in tests:
        attached[row["unique_id"]].append(row["attached_node"])
        if row.get("primary"):
            primary[row["unique_id"]] = row["attached_node"]

    found: list[dict] = []
    for row in results:
        status = str(row.get("status") or "").lower()
        resource_type = str(row.get("resource_type") or "")
        unique_id = row["unique_id"]
        if resource_type == "model" and status == "error":
            found.append(
                {
                    "check_id": unique_id,
                    "kind": "model",
                    "status": status,
                    "node": unique_id,
                    "severity": None,
                }
            )
            continue
        if resource_type != "test":
            continue
        severity = str(row.get("severity") or "").lower()
        if severity != "error" or status not in {"fail", "error"}:
            continue
        models = attached.get(unique_id) or []
        if not models:
            raise ValueError(
                f"error-severity test {unique_id} does not depend on a model."
            )
        found.append(
            {
                "check_id": unique_id,
                "kind": "test",
                "status": status,
                "node": _most_downstream(models, graph, primary.get(unique_id)),
                "severity": severity,
            }
        )

    for row in freshness or []:
        status = str(row.get("status") or "").lower()
        if status != "error":
            continue
        found.append(
            {
                "check_id": row["unique_id"],
                "kind": "freshness",
                "status": status,
                "node": row["unique_id"],
                "severity": None,
            }
        )
    return found


def _most_downstream(candidates: list[str], graph: dict, primary: str | None) -> str:
    """The candidate that sits furthest downstream.

    A reconciliation test depends on a staging model and the mart. The mart
    is the failure we want: it is not an ancestor of the staging model, and
    the staging model is an ancestor of the mart. Sibling models (a
    relationships test) have no such order. Then ``primary`` is the model
    dbt attached the test to. With no primary, the alphabetically last id
    wins so the choice does not depend on row order.
    """
    unique: list[str] = []
    seen: set[str] = set()
    for node in candidates:
        if node in seen:
            continue
        seen.add(node)
        unique.append(node)
    if len(unique) == 1:
        return unique[0]

    downstream = {node: set(descendants(node, graph)) for node in unique}
    sinks = [
        node
        for node in unique
        if not any(other in downstream[node] for other in unique if other != node)
    ]
    if len(sinks) == 1:
        return sinks[0]
    if primary in sinks:
        return primary
    return sorted(sinks)[-1]


def _closure(unique_id: str, graph: dict, depth: int, direction: str) -> list[str]:
    _check_depth(depth)
    nodes, parents, children = _adjacency(graph)
    neighbors = parents if direction == "upstream" else children
    found = _within(unique_id, neighbors, depth)
    if not found:
        return []
    order = _topological_order(nodes, parents, children)
    return [node for node in order if node in found]


def _check_depth(depth: int) -> None:
    if isinstance(depth, bool) or not isinstance(depth, int):
        raise TypeError(f"depth must be an int; got {depth!r}.")
    if depth < 0:
        raise ValueError(f"depth must be zero or greater; got {depth}.")


def _hop_ceiling(nodes: set[str]) -> int:
    """Longest simple path in a DAG is shorter than the node count."""
    return max(len(nodes), 1)


def _adjacency(
    graph: dict,
) -> tuple[set[str], dict[str, set[str]], dict[str, set[str]]]:
    parents: dict[str, set[str]] = defaultdict(set)
    children: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set(graph.get("nodes") or [])
    for edge in graph.get("edges") or []:
        parent = edge["parent"]
        child = edge["child"]
        parents[child].add(parent)
        children[parent].add(child)
        nodes.add(parent)
        nodes.add(child)
    return nodes, parents, children


def _within(start: str, neighbors: dict[str, set[str]], depth: int) -> set[str]:
    found: set[str] = set()
    frontier = [start]
    seen = {start}
    for _hop in range(depth):
        nxt: list[str] = []
        for node in frontier:
            for other in sorted(neighbors.get(node, ())):
                if other in seen:
                    continue
                seen.add(other)
                found.add(other)
                nxt.append(other)
        frontier = nxt
        if not frontier:
            break
    return found


def _ancestors(unique_id: str, parents: dict[str, set[str]]) -> set[str]:
    found: set[str] = set()
    stack = list(parents.get(unique_id, ()))
    while stack:
        node = stack.pop()
        if node in found:
            continue
        found.add(node)
        stack.extend(parents.get(node, ()))
    return found


def _topological_order(
    nodes: set[str],
    parents: dict[str, set[str]],
    children: dict[str, set[str]],
) -> list[str]:
    indegree = {node: len(parents.get(node, ())) for node in nodes}
    ready = sorted(node for node in nodes if indegree[node] == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(children.get(node, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                _insert_sorted(ready, child)
    if len(order) != len(nodes):
        leftover = ", ".join(sorted(nodes - set(order)))
        raise ValueError(f"lineage cycle involving: {leftover}")
    return order


def _insert_sorted(ready: list[str], unique_id: str) -> None:
    """Keep ``ready`` alphabetically sorted. ``unique_id`` is not already in it."""
    for index, current in enumerate(ready):
        if unique_id < current:
            ready.insert(index, unique_id)
            return
    ready.append(unique_id)
