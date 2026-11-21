import type { Artifacts } from "../api/types";
import { copy } from "../copy";
import { formatCost, formatCount, formatElapsed } from "../run/format";
import type { RunView } from "../run/types";

export interface SummaryTile {
  key: string;
  label: string;
  value: string;
}

function countMatch(summary: string | null | undefined, pattern: RegExp): number | null {
  if (!summary) return null;
  const match = pattern.exec(summary);
  if (!match?.[1]) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function shown(value: number | null): string {
  return value == null ? copy.emdash : formatCount(value);
}

function hasRunSignal(view: RunView | null): boolean {
  if (!view) return false;
  if (view.run.elapsed_ms > 0 || view.run.llm_calls > 0) return true;
  if (view.run.cost_usd != null && view.run.cost_usd > 0) return true;
  return Object.values(view.nodes).some(
    (node) => node.attempts > 0 || node.state === "done" || node.state === "failed" || node.state === "running",
  );
}

export function summaryTiles(view: RunView | null, artifacts: Artifacts | null): SummaryTile[] | null {
  if (!artifacts && !hasRunSignal(view)) return null;

  const tables = countMatch(view?.nodes.profile?.summary, /^(\d+) tables\b/);
  let models: number | null = null;
  let tests: number | null = null;
  let built: number | null = null;
  let gaps: number | null = null;

  if (artifacts) {
    models = artifacts.models.length;
    tests = artifacts.tests_passed;
    built = artifacts.kpis.filter((kpi) => kpi.status === "built").length;
    gaps = artifacts.kpis.filter((kpi) => kpi.status === "gap").length;
  } else if (view) {
    models =
      countMatch(view.nodes.write_silver?.summary, /^(\d+) models written\b/) ??
      countMatch(view.nodes.propose?.summary, /(\d+) models\b/);
    tests =
      countMatch(view.nodes.dbt_build_gold?.summary, /^(\d+) tests passed\b/) ??
      countMatch(view.nodes.dbt_build_silver?.summary, /^(\d+) tests passed\b/);
    const gold = /^(\d+) KPIs built · (\d+) gaps\b/.exec(view.nodes.write_gold?.summary ?? "");
    if (gold?.[1] && gold[2]) {
      built = Number(gold[1]);
      gaps = Number(gold[2]);
    }
  }

  return [
    { key: "elapsed", label: copy.elapsed, value: view ? formatElapsed(view.run.elapsed_ms) : copy.emdash },
    { key: "tables", label: copy.views.tables, value: shown(tables) },
    { key: "models", label: copy.views.models, value: shown(models) },
    { key: "tests", label: copy.views.tests, value: shown(tests) },
    { key: "kpis", label: copy.views.kpisBuilt, value: shown(built) },
    { key: "gaps", label: copy.views.gaps, value: shown(gaps) },
    { key: "calls", label: copy.llmCalls, value: view ? formatCount(view.run.llm_calls) : copy.emdash },
    { key: "cost", label: copy.cost, value: view ? formatCost(view.run.cost_usd) : copy.emdash },
  ];
}
