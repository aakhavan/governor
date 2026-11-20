import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "./base";
import type { RunEvent } from "../run/types";

const EVENT_TYPES = [
  "message",
  "run_started",
  "node_started",
  "node_finished",
  "node_failed",
  "run_paused",
  "run_resumed",
  "run_finished",
] as const;

const RECONNECT_MS = 400;

export interface RunEventOptions {
  replay: boolean;
  speed: number;
}

export interface RunEventState {
  events: RunEvent[];
  status: "connecting" | "open" | "reconnecting" | "closed";
  restart: () => void;
}

type StreamInit = EventSourceInit & { headers?: Record<string, string> };

function streamUrl(runId: string, replay: boolean, speed: number): string {
  // EventSource cannot set Authorization. This API does not read a token query
  // parameter, so the dev server and the public demo use GOVERNOR_CONSOLE_OPEN=1.
  // VITE_API_TOKEN is sent on the JSON routes, which use fetch.
  const params = new URLSearchParams({
    replay: replay ? "1" : "0",
    speed: String(speed),
  });
  return apiUrl(`/v1/console/runs/${encodeURIComponent(runId)}/events?${params.toString()}`);
}

function seqFrom(event: MessageEvent, payload: RunEvent | null): number | null {
  if (payload && typeof payload.seq === "number" && Number.isInteger(payload.seq)) return payload.seq;
  if (event.lastEventId && /^\d+$/.test(event.lastEventId)) return Number(event.lastEventId);
  return null;
}

export function useRunEvents(runId: string | null, options: RunEventOptions): RunEventState {
  const { replay, speed } = options;
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<RunEventState["status"]>("connecting");
  const [nonce, setNonce] = useState(0);
  const seenRef = useRef(new Set<number>());
  const lastRef = useRef<number | null>(null);
  const finishedRef = useRef(false);

  const restart = useCallback(() => {
    seenRef.current = new Set();
    lastRef.current = null;
    finishedRef.current = false;
    setEvents([]);
    setStatus("connecting");
    setNonce((value) => value + 1);
  }, []);

  useEffect(() => {
    seenRef.current = new Set();
    lastRef.current = null;
    finishedRef.current = false;
    setEvents([]);
    setStatus("connecting");
  }, [runId, nonce]);

  useEffect(() => {
    if (!runId) return undefined;
    let alive = true;
    let source: EventSource | null = null;
    let timer = 0;
    const url = streamUrl(runId, replay, speed);

    const open = () => {
      if (!alive) return;
      const last = lastRef.current;
      const init: StreamInit | undefined = last != null ? { headers: { "Last-Event-ID": String(last) } } : undefined;
      const Source = globalThis.EventSource;
      source = new Source(url, init as EventSourceInit | undefined);
      const onEvent = (raw: Event) => {
        if (!alive) return;
        const message = raw as MessageEvent;
        let payload: RunEvent | null = null;
        try {
          const parsed = JSON.parse(String(message.data)) as unknown;
          if (parsed && typeof parsed === "object") payload = parsed as RunEvent;
        } catch {
          payload = null;
        }
        const seq = seqFrom(message, payload);
        if (seq != null) {
          if (seenRef.current.has(seq)) return;
          seenRef.current.add(seq);
          lastRef.current = seq;
        }
        if (!payload) return;
        if (payload.type === "run_finished") finishedRef.current = true;
        setStatus("open");
        setEvents((current) => [...current, payload]);
      };
      for (const type of EVENT_TYPES) source.addEventListener(type, onEvent);
      source.onopen = () => {
        if (alive) setStatus("open");
      };
      const again = () => {
        if (!alive) return;
        setStatus("reconnecting");
        window.clearTimeout(timer);
        timer = window.setTimeout(open, RECONNECT_MS);
      };
      source.onerror = () => {
        source?.close();
        again();
      };
      source.addEventListener("end", () => {
        if (!alive) return;
        if (!replay && !finishedRef.current) again();
        else setStatus("closed");
      });
    };

    open();
    return () => {
      alive = false;
      window.clearTimeout(timer);
      source?.close();
    };
  }, [runId, nonce, replay, speed]);

  return { events, status, restart };
}
