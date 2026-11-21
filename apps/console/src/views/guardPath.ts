import type { RunEvent, RunView } from "../run/types";

export const GUARD_CHECKS = ["guard", "validate", "dry_run", "execute", "answer"] as const;
export type CheckId = (typeof GUARD_CHECKS)[number];

export type GuardRow =
  | { kind: "check"; id: CheckId; outcome: "pass" | "refused"; code: string | null }
  | { kind: "repair"; text: string }
  | { kind: "pending"; id: CheckId };

function isCheck(node: string | null | undefined): node is CheckId {
  return node != null && (GUARD_CHECKS as readonly string[]).includes(node);
}

function codeAfter(summary: string, prefix: string): string | null {
  const code = summary.slice(prefix.length).replace(/^:\s*/, "").trim();
  return code || null;
}

function judgeExecute(summary: string, later: readonly RunEvent[]): { outcome: "pass" | "refused"; code: string | null } {
  const match = /^(\d+) rows$/.exec(summary);
  if (!match?.[1]) return { outcome: "refused", code: summary || null };
  if (Number(match[1]) > 0) return { outcome: "pass", code: null };
  const answered = later.some((event) => event.node === "answer" && event.type === "node_finished");
  if (answered) return { outcome: "pass", code: null };
  const repaired = later.some((event) => event.node === "repair" && event.type === "node_finished");
  const refused = later.some(
    (event) => event.type === "run_finished" && (event.status === "refused" || event.status === "failed"),
  );
  if (repaired || refused) return { outcome: "refused", code: null };
  return { outcome: "pass", code: null };
}

function judge(
  id: CheckId,
  summary: string | null,
  errorCode: string | null,
  later: readonly RunEvent[],
): { outcome: "pass" | "refused"; code: string | null } {
  if (errorCode) return { outcome: "refused", code: errorCode };
  const text = summary?.trim() ?? "";
  if (id === "guard") {
    if (text === "ok") return { outcome: "pass", code: null };
    if (text.startsWith("blocked")) return { outcome: "refused", code: codeAfter(text, "blocked") };
    return { outcome: "refused", code: text || null };
  }
  if (id === "validate") {
    if (text === "ok") return { outcome: "pass", code: null };
    if (text.startsWith("refused")) return { outcome: "refused", code: codeAfter(text, "refused") };
    return { outcome: "refused", code: text || null };
  }
  if (id === "dry_run") {
    if (text === "ok") return { outcome: "pass", code: null };
    return { outcome: "refused", code: text || null };
  }
  if (id === "execute") return judgeExecute(text, later);
  if (text === "answered") return { outcome: "pass", code: null };
  return { outcome: "refused", code: text || null };
}

function rowsFromEvents(events: readonly RunEvent[]): GuardRow[] | null {
  const rows: GuardRow[] = [];
  const reached = new Set<CheckId>();
  events.forEach((event, index) => {
    if (event.type === "node_finished" && event.node === "repair") {
      rows.push({ kind: "repair", text: event.summary?.trim() ?? "" });
      return;
    }
    if (!isCheck(event.node)) return;
    if (event.type !== "node_finished" && event.type !== "node_failed") return;
    const later = events.slice(index + 1);
    const outcome =
      event.type === "node_failed"
        ? { outcome: "refused" as const, code: event.error_code ?? null }
        : judge(event.node, event.summary ?? null, event.error_code ?? null, later);
    rows.push({ kind: "check", id: event.node, ...outcome });
    reached.add(event.node);
  });
  if (rows.length === 0) return null;
  for (const id of GUARD_CHECKS) {
    if (!reached.has(id)) rows.push({ kind: "pending", id });
  }
  return rows;
}

function rowsFromView(view: RunView): GuardRow[] | null {
  const repair = view.nodes.repair;
  const active = GUARD_CHECKS.some((id) => {
    const node = view.nodes[id];
    return node != null && node.state !== "pending" && node.state !== "skipped" && node.attempts > 0;
  });
  if (!active && repair?.state !== "done") return null;
  const rows: GuardRow[] = [];
  for (const id of GUARD_CHECKS) {
    const node = view.nodes[id];
    if (!node || node.state === "pending" || node.state === "skipped" || node.attempts === 0) {
      rows.push({ kind: "pending", id });
      continue;
    }
    if (node.state === "failed") {
      rows.push({ kind: "check", id, outcome: "refused", code: node.error_code });
      continue;
    }
    if (node.state !== "done") {
      rows.push({ kind: "pending", id });
      continue;
    }
    rows.push({ kind: "check", id, ...judge(id, node.summary, node.error_code, []) });
  }
  if (repair?.state === "done") {
    const validateAt = rows.findIndex((row) => row.kind === "check" && row.id === "validate");
    rows.splice(validateAt >= 0 ? validateAt + 1 : 1, 0, { kind: "repair", text: repair.summary ?? "" });
  }
  return rows;
}

export function guardRows(events: readonly RunEvent[], view: RunView | null): GuardRow[] | null {
  return rowsFromEvents(events) ?? (view ? rowsFromView(view) : null);
}
