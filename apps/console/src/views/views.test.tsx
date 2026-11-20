import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Artifacts } from "../api/types";
import { copy, statusText } from "../copy";
import { fold } from "../run/fold";
import type { RunEvent, RunView } from "../run/types";
import { FunnelView } from "./FunnelView";
import { GuardPathView } from "./GuardPathView";
import { KpiEvidenceView } from "./KpiEvidenceView";
import { LineageView } from "./LineageView";
import { SummaryView } from "./SummaryView";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const artifacts = JSON.parse(readFileSync(resolve(root, "tests/fixtures/console/build-full.artifacts.json"), "utf8")) as Artifacts;
const askEvents = JSON.parse(readFileSync(resolve(root, "tests/fixtures/console/ask-repaired.events.json"), "utf8")) as RunEvent[];

function runView(): RunView {
  return {
    run: {
      state: "finished",
      status: "built",
      elapsed_ms: 90_000,
      llm_calls: 3,
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: 0.02,
      current_node: null,
    },
    nodes: {
      profile: {
        state: "done",
        attempts: 1,
        duration_ms: 40,
        summary: "9 tables · 52 columns · 12 PII",
        error_code: null,
      },
    },
  };
}

function tile(label: string): HTMLElement {
  const item = screen.getByText(label).closest("li");
  if (!item) throw new Error(label);
  return item;
}

describe("SummaryView renders", () => {
  it("shows tiles from the demo artifacts", () => {
    render(<SummaryView view={runView()} artifacts={artifacts} />);
    const built = artifacts.kpis.filter((kpi) => kpi.status === "built").length;
    const gaps = artifacts.kpis.filter((kpi) => kpi.status === "gap").length;
    expect(tile(copy.views.tables)).toHaveTextContent("9");
    expect(tile(copy.views.models)).toHaveTextContent(String(artifacts.models.length));
    expect(tile(copy.views.tests)).toHaveTextContent(String(artifacts.tests_passed));
    expect(tile(copy.views.kpisBuilt)).toHaveTextContent(String(built));
    expect(tile(copy.views.gaps)).toHaveTextContent(String(gaps));
    expect(tile(copy.elapsed)).toHaveTextContent("1m 30s");
  });

  it("keeps the summary when the build has no artifacts", () => {
    render(<SummaryView view={runView()} artifacts={null} />);
    expect(screen.queryByText(copy.views.summaryEmpty)).not.toBeInTheDocument();
    expect(tile(copy.views.tables)).toHaveTextContent("9");
    expect(tile(copy.elapsed)).toHaveTextContent("1m 30s");
    expect(tile(copy.llmCalls)).toHaveTextContent("3");
    expect(tile(copy.views.tests)).toHaveTextContent(copy.emdash);
  });
});

describe("LineageView renders", () => {
  it("draws layers, a dashed gap, and the connected path", () => {
    render(<LineageView artifacts={artifacts} />);
    expect(screen.getByText(copy.views.layerRaw)).toBeInTheDocument();
    expect(screen.getByText(copy.views.layerGold)).toBeInTheDocument();
    const gap = artifacts.kpis.find((kpi) => kpi.status === "gap");
    if (!gap) throw new Error("gap");
    expect(screen.getByRole("button", { name: gap.id })).toHaveClass("is-gap");

    const focus = artifacts.lineage.nodes.find(
      (node) =>
        artifacts.lineage.edges.some((edge) => edge.target === node.id) &&
        artifacts.lineage.edges.some((edge) => edge.source === node.id),
    );
    if (!focus) throw new Error("focus");
    fireEvent.click(screen.getByRole("button", { name: focus.id }));
    const upstream = artifacts.lineage.edges.find((edge) => edge.target === focus.id);
    if (!upstream) throw new Error("upstream");
    expect(screen.getByRole("button", { name: focus.id })).toHaveClass("is-hot");
    expect(screen.getByRole("button", { name: upstream.source })).toHaveClass("is-hot");
    expect(document.querySelector("button.lineage-node.is-dim")).not.toBeNull();
  });
});

describe("FunnelView renders", () => {
  it("shows the stage counts and what the guard rails stopped", () => {
    render(<FunnelView artifacts={artifacts} />);
    expect(screen.getByText(copy.views.funnelStopped)).toBeInTheDocument();
    expect(screen.getByText(copy.views.funnelClear)).toBeInTheDocument();
    const requested = screen.getByText(copy.views.requested).closest("li");
    expect(requested).toHaveTextContent(String(artifacts.funnel.requested));
    const built = screen.getByText(copy.views.built).closest("li");
    expect(built).toHaveTextContent(String(artifacts.funnel.built));
  });
});

describe("KpiEvidenceView renders", () => {
  it("shows a card for each demo KPI", () => {
    render(<KpiEvidenceView artifacts={artifacts} />);
    const built = artifacts.kpis.find((kpi) => kpi.status === "built" && kpi.models.length > 0);
    const gap = artifacts.kpis.find((kpi) => kpi.status === "gap");
    if (!built || !gap) throw new Error("kpi");
    expect(screen.getByRole("heading", { name: built.id })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: gap.id })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: built.id }).closest("li")).toHaveTextContent(built.models[0] ?? "");
    expect(screen.getAllByText(statusText("built")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(statusText("gap")).length).toBeGreaterThan(0);
    expect(screen.getByText(statusText("declined"))).toBeInTheDocument();
  });
});

describe("GuardPathView renders", () => {
  it("shows passes, a refusal code, and the repair between them", () => {
    render(<GuardPathView view={fold(askEvents)} events={askEvents} />);
    expect(screen.getByText("COLUMN_UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("repair 1")).toBeInTheDocument();
    expect(screen.getAllByText(copy.views.checkValidate)).toHaveLength(2);
    expect(screen.getByText(copy.views.checkGuard)).toBeInTheDocument();
    expect(screen.getByText(copy.views.checkDryRun)).toBeInTheDocument();
    expect(screen.getByText(copy.views.checkExecute)).toBeInTheDocument();
    expect(screen.getByText(copy.views.checkAnswer)).toBeInTheDocument();
    expect(screen.getAllByText(statusText("pass")).length).toBeGreaterThan(1);
    expect(screen.getByText(statusText("refused"))).toBeInTheDocument();
  });
});

describe("empty state", () => {
  it("says what to do when the data is missing", () => {
    render(<SummaryView view={null} artifacts={null} />);
    expect(screen.getByText(copy.views.summaryEmpty)).toBeInTheDocument();
    cleanup();
    render(<LineageView artifacts={null} />);
    expect(screen.getByText(copy.views.lineageEmpty)).toBeInTheDocument();
    cleanup();
    render(<FunnelView artifacts={null} />);
    expect(screen.getByText(copy.views.funnelEmpty)).toBeInTheDocument();
    cleanup();
    render(<KpiEvidenceView artifacts={null} />);
    expect(screen.getByText(copy.views.kpiEmpty)).toBeInTheDocument();
    cleanup();
    render(<GuardPathView view={null} events={[]} />);
    expect(screen.getByText(copy.views.guardEmpty)).toBeInTheDocument();
  });
});

describe("captions come from copy", () => {
  it("uses the caption strings", () => {
    const cases: { caption: string; node: JSX.Element }[] = [
      { caption: copy.views.summaryCaption, node: <SummaryView view={null} artifacts={null} /> },
      { caption: copy.views.lineageCaption, node: <LineageView artifacts={null} /> },
      { caption: copy.views.funnelCaption, node: <FunnelView artifacts={null} /> },
      { caption: copy.views.kpiCaption, node: <KpiEvidenceView artifacts={null} /> },
      { caption: copy.views.guardCaption, node: <GuardPathView view={null} events={[]} /> },
    ];
    for (const item of cases) {
      render(item.node);
      expect(screen.getByText(item.caption)).toBeInTheDocument();
      cleanup();
    }
  });
});
