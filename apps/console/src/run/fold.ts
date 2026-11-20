import type { NodeView, RunTotals, RunView } from "./types";

/**
 * Non-planned build and ask node ids, in registry order.
 * Start and end are drawn on the canvas but are not part of this skip list.
 */
const BUILD_NODE_IDS = [
  "profile",
  "compare",
  "propose",
  "validate",
  "write_report",
  "design_gate",
  "record_decisions",
  "write_silver",
  "dbt_build_silver",
  "repair_silver",
  "silver_done",
  "write_gold",
  "dbt_build_gold",
  "summarise",
] as const;

const ASK_NODE_IDS = [
  "guard",
  "retrieve_context",
  "plan",
  "clarify",
  "draft_sql",
  "validate",
  "dry_run",
  "repair",
  "execute",
  "answer",
  "record_trace",
] as const;

function blank(state: NodeView["state"] = "pending"): NodeView {
  return { state, attempts: 0, duration_ms: 0, summary: null, error_code: null };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function seqOf(event: Record<string, unknown>): number | null {
  const seq = event.seq;
  if (typeof seq !== "number" || !Number.isInteger(seq)) return null;
  return seq;
}

function applyOrder(events: readonly Record<string, unknown>[]): Record<string, unknown>[] {
  const tagged = events.map((event, index) => ({ event, index }));
  tagged.sort((left, right) => {
    const leftSeq = seqOf(left.event);
    const rightSeq = seqOf(right.event);
    if (leftSeq != null && rightSeq != null) {
      if (leftSeq !== rightSeq) return leftSeq - rightSeq;
      return left.index - right.index;
    }
    if (leftSeq != null) return -1;
    if (rightSeq != null) return 1;
    return left.index - right.index;
  });
  const seen = new Set<number>();
  const applied: Record<string, unknown>[] = [];
  for (const { event } of tagged) {
    if (!isRecord(event)) continue;
    const seq = seqOf(event);
    if (seq != null) {
      if (seen.has(seq)) continue;
      seen.add(seq);
    }
    applied.push(event);
  }
  return applied;
}

function milliseconds(value: unknown): number | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const trimmed = value.trim();
  const zoned = /(?:Z|[+-]\d{2}:\d{2})$/.test(trimmed) ? trimmed : `${trimmed}Z`;
  const parsed = Date.parse(zoned);
  return Number.isNaN(parsed) ? null : parsed;
}

function asNumber(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.round(value * 1e6) / 1e6;
}

function asInt(value: unknown): number | null {
  const number = asNumber(value);
  if (number == null) return null;
  return Math.trunc(number);
}

function whole(value: number): number {
  const rounded = Math.round(value * 1e6) / 1e6;
  return Object.is(rounded, -0) ? 0 : rounded;
}

function catalog(graph: string | null): readonly string[] {
  if (graph === "build") return BUILD_NODE_IDS;
  if (graph === "ask") return ASK_NODE_IDS;
  return [];
}

function unrecovered(events: readonly Record<string, unknown>[]): boolean {
  let lastFail = -1;
  let lastStart = -1;
  events.forEach((event, index) => {
    if (event.type === "node_failed") lastFail = index;
    else if (event.type === "node_started") lastStart = index;
  });
  return lastFail >= 0 && lastFail > lastStart;
}

export function fold(events: readonly object[] | null | undefined): RunView {
  const records: Record<string, unknown>[] = [];
  for (const event of events ?? []) {
    if (isRecord(event)) records.push(event);
  }
  const applied = applyOrder(records);
  const nodes: Record<string, NodeView> = {};
  const recent: string[] = [];
  let lifecycle: RunTotals["state"] = "running";
  let status: string | null = null;
  let finished = false;
  let graph: string | null = null;
  let llmCalls = 0;
  let tokensIn = 0;
  let tokensOut = 0;
  let cost = 0;
  let costUnknown = false;

  const touch = (nodeId: string) => {
    const index = recent.indexOf(nodeId);
    if (index >= 0) recent.splice(index, 1);
    recent.push(nodeId);
  };

  const ensure = (nodeId: unknown): NodeView | null => {
    if (typeof nodeId !== "string" || !nodeId) return null;
    nodes[nodeId] ??= blank();
    return nodes[nodeId];
  };

  for (const event of applied) {
    if (graph === null && typeof event.graph === "string") graph = event.graph;
    const kind = event.type;
    const node = event.node ? ensure(event.node) : null;
    if (kind === "node_started" && node) {
      node.state = "running";
      node.attempts += 1;
      if (typeof event.node === "string") touch(event.node);
    } else if (kind === "node_finished" && node) {
      node.state = "done";
      if (typeof event.duration_ms === "number" && Number.isInteger(event.duration_ms)) {
        node.duration_ms += event.duration_ms;
      }
      if (typeof event.summary === "string" && event.summary) node.summary = event.summary;
      if (isRecord(event.metrics)) {
        const metrics = event.metrics;
        const calls = asInt(metrics.llm_calls);
        const into = asInt(metrics.tokens_in);
        const out = asInt(metrics.tokens_out);
        if (calls != null) llmCalls += calls;
        if (into != null) tokensIn += into;
        if (out != null) tokensOut += out;
        if ("cost_usd" in metrics) {
          if (metrics.cost_usd == null) costUnknown = true;
          else {
            const part = asNumber(metrics.cost_usd);
            if (part == null) costUnknown = true;
            else cost += part;
          }
        }
      }
    } else if (kind === "node_failed" && node) {
      node.state = "failed";
      if (typeof event.error_code === "string" && event.error_code) node.error_code = event.error_code;
    } else if (kind === "run_paused") {
      lifecycle = "paused";
      if (typeof event.status === "string") status = event.status;
      if (node && typeof event.node === "string") {
        node.state = "paused";
        touch(event.node);
      }
    } else if (kind === "run_resumed") {
      lifecycle = "running";
      status = null;
    } else if (kind === "run_finished") {
      lifecycle = "finished";
      finished = true;
      if (typeof event.status === "string") status = event.status;
    }
  }

  if (unrecovered(applied)) lifecycle = "failed";
  if (finished) {
    for (const nodeId of catalog(graph)) {
      const current = nodes[nodeId];
      if (!current) nodes[nodeId] = blank("skipped");
      else if (current.attempts === 0) current.state = "skipped";
    }
  }

  const stamps = applied.map((event) => milliseconds(event.ts)).filter((stamp): stamp is number => stamp != null);
  const elapsed = stamps.length >= 2 ? Math.max(0, stamps[stamps.length - 1] - stamps[0]) : 0;
  let currentNode: string | null = null;
  for (let index = recent.length - 1; index >= 0; index -= 1) {
    const nodeId = recent[index];
    const state = nodes[nodeId]?.state;
    if (state === "running" || state === "paused") {
      currentNode = nodeId;
      break;
    }
  }
  const costUsd = costUnknown ? null : whole(cost);
  return {
    run: {
      state: lifecycle,
      status,
      elapsed_ms: elapsed,
      llm_calls: llmCalls,
      tokens_in: tokensIn,
      tokens_out: tokensOut,
      cost_usd: costUsd,
      current_node: currentNode,
    },
    nodes,
  };
}
