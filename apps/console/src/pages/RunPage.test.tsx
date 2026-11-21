import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RunSummary, Topology } from "../api/types";
import type { RunEvent } from "../run/types";
import { RunPage } from "./RunPage";

vi.mock("../api/client", () => ({
  listRuns: vi.fn(),
  getTopology: vi.fn(),
  getRun: vi.fn(),
  getArtifacts: vi.fn(),
}));

import { getTopology, listRuns } from "../api/client";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const demo = JSON.parse(readFileSync(resolve(root, "tests/fixtures/console/demo_run.json"), "utf8")) as {
  run_id: string;
  graph: "build";
  source: "demo";
  started: string;
  last_event: string;
  status: string;
  elapsed_ms: number;
  cost_usd: number;
  llm_calls: number;
  events: RunEvent[];
};
const topology = JSON.parse(readFileSync(resolve(root, "tests/fixtures/console/topology_build.json"), "utf8")) as Topology;

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  private listeners = new Map<string, Array<(event: MessageEvent) => void>>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    queueMicrotask(() => {
      for (const event of demo.events) {
        const type = event.type ?? "message";
        const message = new MessageEvent(type, { data: JSON.stringify(event), lastEventId: String(event.seq ?? "") });
        for (const listener of this.listeners.get(type) ?? []) listener(message);
      }
    });
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }

  removeEventListener() {}

  close() {}
}

describe("RunPage renders demo run", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    const summary: RunSummary = {
      run_id: demo.run_id,
      graph: demo.graph,
      started: demo.started,
      last_event: demo.last_event,
      status: demo.status,
      elapsed_ms: demo.elapsed_ms,
      cost_usd: demo.cost_usd,
      llm_calls: demo.llm_calls,
      source: demo.source,
    };
    vi.mocked(listRuns).mockResolvedValue([summary]);
    vi.mocked(getTopology).mockResolvedValue(topology);
  });

  it("shows the demo run from the fixtures", async () => {
    render(
      <MemoryRouter initialEntries={[`/runs/${demo.run_id}`]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/runs/:runId" element={<RunPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: demo.run_id })).toBeInTheDocument();
    expect(await screen.findByText("Up to date")).toBeInTheDocument();
    expect(await screen.findByText("Profile")).toBeInTheDocument();
    expect(await screen.findByRole("tab", { name: "Steps" })).toBeInTheDocument();
  });
});
