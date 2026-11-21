import { graphlib, layout as dagreLayout } from "@dagrejs/dagre";

export const NODE_WIDTH = 230;
export const NODE_HEIGHT = 68;

export type Direction = "LR" | "TB";

export function placeNodes(
  ids: readonly string[],
  edges: readonly { source: string; target: string }[],
  direction: Direction,
): Map<string, { x: number; y: number }> {
  const graph = new graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: direction, nodesep: 32, ranksep: 100, marginx: 12, marginy: 12 });
  const known = new Set(ids);
  for (const id of ids) graph.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  const seen = new Set<string>();
  for (const edge of edges) {
    if (!known.has(edge.source) || !known.has(edge.target)) continue;
    const key = `${edge.source}\0${edge.target}`;
    if (seen.has(key)) continue;
    seen.add(key);
    graph.setEdge(edge.source, edge.target);
  }
  dagreLayout(graph);
  const positions = new Map<string, { x: number; y: number }>();
  for (const id of ids) {
    const placed = graph.node(id);
    if (!placed || !Number.isFinite(placed.x) || !Number.isFinite(placed.y)) continue;
    positions.set(id, { x: placed.x - NODE_WIDTH / 2, y: placed.y - NODE_HEIGHT / 2 });
  }
  return positions;
}
