import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GovernorNode, type GovernorFlowNode } from "./GovernorNode";
import type { GovernorData } from "./nodeState";
import type { NodeProps } from "@xyflow/react";

vi.mock("@xyflow/react", () => ({
  Handle: () => null,
  Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
}));

function data(overrides: Partial<GovernorData>): GovernorData {
  return {
    label: "Profile",
    kind: "io",
    description: "Reads the raw schema: table, column and PII counts.",
    group: "design",
    state: "pending",
    attempts: 1,
    durationMs: 0,
    summary: null,
    errorCode: null,
    pauseStatus: null,
    mode: "run",
    ...overrides,
  };
}

function renderNode(overrides: Partial<GovernorData>) {
  const props = { data: data(overrides) } as NodeProps<GovernorFlowNode>;
  return render(<GovernorNode {...props} />);
}

describe("GovernorNode states", () => {
  it("renders pending", () => {
    const { container } = renderNode({ state: "pending", attempts: 0 });
    expect(container.querySelector(".node-pending")).toBeTruthy();
    expect(screen.getByText("Not started")).toBeInTheDocument();
  });

  it("renders running", () => {
    const { container } = renderNode({ state: "running" });
    expect(container.querySelector(".node-running")).toBeTruthy();
    expect(screen.getByText("Working…")).toBeInTheDocument();
  });

  it("renders done", () => {
    const { container } = renderNode({ state: "done", summary: "2 tables", durationMs: 40 });
    expect(container.querySelector(".node-done")).toBeTruthy();
    expect(screen.getByText("2 tables")).toBeInTheDocument();
    expect(screen.getByText("40 ms")).toBeInTheDocument();
  });

  it("renders failed", () => {
    const { container } = renderNode({ state: "failed", errorCode: "ValueError" });
    expect(container.querySelector(".node-failed")).toBeTruthy();
    expect(screen.getByText("ValueError")).toBeInTheDocument();
  });

  it("renders paused for approval", () => {
    const { container } = renderNode({ state: "paused", pauseStatus: "awaiting_approval" });
    expect(container.querySelector(".node-paused")).toBeTruthy();
    expect(screen.getByText("Waiting for approval")).toBeInTheDocument();
  });

  it("renders paused for an answer", () => {
    const { container } = renderNode({ state: "paused", pauseStatus: "awaiting_clarification" });
    expect(container.querySelector(".node-paused")).toBeTruthy();
    expect(screen.getByText("Waiting for an answer")).toBeInTheDocument();
  });

  it("renders skipped", () => {
    const { container } = renderNode({ state: "skipped", attempts: 0 });
    expect(container.querySelector(".node-skipped")).toBeTruthy();
    expect(screen.getByText("Skipped")).toBeInTheDocument();
  });

  it("renders planned", () => {
    const { container } = renderNode({ state: "planned", mode: "topology", attempts: 0 });
    expect(container.querySelector(".node-planned")).toBeTruthy();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
  });

  it("renders the attempt badge", () => {
    renderNode({ state: "done", attempts: 2, summary: "repair 2" });
    expect(screen.getByText("×2")).toBeInTheDocument();
  });
});
