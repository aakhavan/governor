import type { CSSProperties } from "react";
import type { Kind } from "../api/types";
import { copy, groupText, nodeAria } from "../copy";
import { KIND_COLOR } from "./kinds";

export type ViewState = "pending" | "running" | "done" | "failed" | "paused" | "skipped" | "planned";

export interface GovernorData extends Record<string, unknown> {
  label: string;
  kind: Kind;
  description: string;
  group: string;
  state: ViewState;
  attempts: number;
  durationMs: number;
  summary: string | null;
  errorCode: string | null;
  pauseStatus: string | null;
  mode: "run" | "topology";
}

export function nodeStatusText(data: GovernorData): string {
  if (data.mode === "topology" && data.state !== "planned") return groupText(data.group);
  switch (data.state) {
    case "pending":
      return copy.nodePending;
    case "running":
      return copy.nodeRunning;
    case "done":
      return data.summary ?? "";
    case "failed":
      return data.errorCode || copy.nodeFailed;
    case "paused":
      return data.pauseStatus === "awaiting_clarification" ? copy.nodePausedAnswer : copy.nodePausedApproval;
    case "skipped":
      return copy.nodeSkipped;
    case "planned":
      return copy.nodePlanned;
    default:
      return "";
  }
}

export function stateLabel(state: ViewState): string {
  switch (state) {
    case "pending":
      return copy.nodePending;
    case "running":
      return copy.nodeRunning;
    case "done":
      return copy.stateDone;
    case "failed":
      return copy.nodeFailed;
    case "paused":
      return copy.statePaused;
    case "skipped":
      return copy.nodeSkipped;
    case "planned":
      return copy.nodePlanned;
    default:
      return "";
  }
}

export function nodeClass(data: GovernorData, selected: boolean): string {
  const names = ["node", `node-${data.state}`, `node-kind-${data.kind}`];
  if (data.mode === "topology") names.push("node-topology");
  if (selected) names.push("is-selected");
  return names.join(" ");
}

export function nodeStyle(data: GovernorData): CSSProperties {
  return { "--kind": KIND_COLOR[data.kind] } as CSSProperties;
}

export function nodeLabel(data: GovernorData): string {
  return nodeAria(data.label, nodeStatusText(data));
}
