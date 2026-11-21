import type { RunEvent } from "../run/types";

export type EdgeVisual = "dim" | "traversed" | "active" | "map";

export interface PillData extends Record<string, unknown> {
  state: EdgeVisual;
}

export function pairKey(source: string, target: string): string {
  return `${source}\0${target}`;
}

/** Edges the run has crossed, and the edge currently entering the active node. */
export function classifyEdges(events: readonly RunEvent[], currentNode: string | null): {
  traversed: Set<string>;
  active: string | null;
} {
  const traversed = new Set<string>();
  const into = new Map<string, string>();
  let previous = "start";
  for (const event of events) {
    if (event.type === "node_started" && event.node) {
      const key = pairKey(previous, event.node);
      traversed.add(key);
      into.set(event.node, key);
      previous = event.node;
    } else if (event.type === "run_finished" && previous) {
      traversed.add(pairKey(previous, "end"));
    }
  }
  const active = currentNode ? into.get(currentNode) ?? null : null;
  return { traversed, active };
}
