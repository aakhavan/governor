import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useRunEvents } from "./useRunEvents";

interface MockInit {
  headers?: Record<string, string>;
}

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  init: MockInit | undefined;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  private listeners = new Map<string, Array<(event: MessageEvent) => void>>();

  constructor(url: string, init?: MockInit) {
    this.url = url;
    this.init = init;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }

  removeEventListener() {}

  close() {}

  emit(type: string, data: unknown, id: string) {
    const event = new MessageEvent(type, { data: JSON.stringify(data), lastEventId: id });
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

describe("useRunEvents dedupe and reconnect", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    MockEventSource.instances = [];
  });

  it("ignores a duplicate seq and reconnects with Last-Event-ID", async () => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useRunEvents("build-full", { replay: true, speed: 4 }));
    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const first = MockEventSource.instances[0];
    expect(first.url).toContain("/v1/console/runs/build-full/events?");
    expect(first.url).toContain("replay=1");
    expect(first.url).toContain("speed=4");
    act(() => {
      first.emit("node_started", { seq: 7, type: "node_started", node: "profile" }, "7");
      first.emit("node_started", { seq: 7, type: "node_started", node: "profile" }, "7");
    });
    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]?.node).toBe("profile");
    act(() => {
      first.onerror?.(new Event("error"));
    });
    await waitFor(() => expect(MockEventSource.instances.length).toBe(2), { timeout: 2000 });
    expect(MockEventSource.instances[1]?.init?.headers?.["Last-Event-ID"]).toBe("7");
  });
});
