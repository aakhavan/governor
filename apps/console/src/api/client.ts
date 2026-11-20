import { apiUrl } from "./base";
import type { Artifacts, GraphName, RunSummary, Topology } from "./types";
import type { RunView } from "../run/types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
  }
}

function headers(): Headers {
  const result = new Headers({ Accept: "application/json" });
  const token = import.meta.env.VITE_API_TOKEN;
  if (token) result.set("Authorization", `Bearer ${token}`);
  return result;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiUrl(path), { headers: headers(), signal });
  if (!response.ok) throw new ApiError(response.status);
  return response.json() as Promise<T>;
}

export function getTopology(graph: GraphName, signal?: AbortSignal): Promise<Topology> {
  return getJson<Topology>(`/v1/console/graphs/${graph}`, signal);
}

export function listRuns(graph?: GraphName, limit = 50, signal?: AbortSignal): Promise<RunSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (graph) params.set("graph", graph);
  return getJson<{ runs: RunSummary[] }>(`/v1/console/runs?${params.toString()}`, signal).then((body) => body.runs);
}

export function getRun(runId: string, signal?: AbortSignal): Promise<RunView> {
  return getJson<RunView>(`/v1/console/runs/${encodeURIComponent(runId)}`, signal);
}

export function getArtifacts(runId: string, signal?: AbortSignal): Promise<Artifacts> {
  return getJson<Artifacts>(`/v1/console/runs/${encodeURIComponent(runId)}/artifacts`, signal);
}
