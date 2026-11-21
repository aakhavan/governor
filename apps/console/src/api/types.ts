import type { RunView } from "../run/types";

export type GraphName = "build" | "ask";
export type Kind = "guard" | "llm" | "check" | "dbt" | "gate" | "io" | "summary";
export type Group = "design" | "silver" | "gold" | "understand" | "sql" | "answer";

export interface TopologyNode {
  id: string;
  label: string;
  kind: Kind;
  description: string;
  group: Group;
  order: number;
  planned: boolean;
}

export interface TopologyEdge {
  source: string;
  target: string;
  label: string;
  conditional: boolean;
}

export interface Topology {
  graph: GraphName;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface RunSummary {
  run_id: string;
  graph: GraphName;
  started: string | null;
  last_event: string | null;
  status: string;
  elapsed_ms: number;
  cost_usd: number | null;
  llm_calls: number;
  source: "live" | "demo";
}

export interface Artifacts {
  kpis: { id: string; status: "built" | "gap" | "declined"; models: string[] }[];
  models: { name: string; layer: "staging" | "silver" | "gold" }[];
  tests_passed: number | null;
  repairs: number | null;
  finding_codes: Record<string, number>;
  funnel: {
    requested: number | null;
    computable: number | null;
    proposed: number | null;
    validated: number | null;
    built: number | null;
  };
  lineage: {
    nodes: { id: string; layer: "raw" | "silver" | "gold" | "kpi" }[];
    edges: { source: string; target: string }[];
  };
}

export type { RunView };
