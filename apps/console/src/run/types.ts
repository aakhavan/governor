export interface RunMetrics {
  llm_calls?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  cost_usd?: number | null;
}

export interface RunEvent {
  v?: number;
  ts?: string;
  run_id?: string;
  graph?: string;
  seq?: number;
  type?: string;
  node?: string | null;
  attempt?: number | null;
  duration_ms?: number | null;
  summary?: string | null;
  status?: string | null;
  metrics?: RunMetrics | null;
  error_code?: string | null;
  target_name?: string | null;
}

export interface NodeView {
  state: "pending" | "running" | "done" | "failed" | "paused" | "skipped";
  attempts: number;
  duration_ms: number;
  summary: string | null;
  error_code: string | null;
}

export interface RunTotals {
  state: "running" | "paused" | "finished" | "failed";
  status: string | null;
  elapsed_ms: number;
  llm_calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  current_node: string | null;
}

export interface RunView {
  run: RunTotals;
  nodes: Record<string, NodeView>;
}
