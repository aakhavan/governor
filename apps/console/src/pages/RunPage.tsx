import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { getArtifacts, getTopology, listRuns } from "../api/client";
import type { Artifacts, RunSummary, Topology, TopologyNode } from "../api/types";
import { useRunEvents } from "../api/useRunEvents";
import { copy, eventText, graphText, runLabel, statusText } from "../copy";
import type { Direction } from "../graph/layout";
import { stateLabel } from "../graph/nodeState";
import { RunCanvas } from "../graph/RunCanvas";
import { fold } from "../run/fold";
import { formatClock, formatCost, formatCount, formatDuration, formatElapsed, statusTone } from "../run/format";
import type { RunEvent, RunView } from "../run/types";
import { ResultPanel } from "../views/ResultPanel";

function isArtifacts(value: unknown): value is Artifacts {
  if (!value || typeof value !== "object") return false;
  const record = value as Partial<Artifacts>;
  return Array.isArray(record.kpis) && Array.isArray(record.models) && record.funnel != null && record.lineage != null;
}

const LIVE = new Set(["running", "paused", "awaiting_approval", "awaiting_clarification"]);
const SPEEDS = [1, 4, 16] as const;
type Speed = (typeof SPEEDS)[number];

function replayByDefault(run: RunSummary): boolean {
  if (LIVE.has(run.status)) return false;
  return run.source === "demo";
}

function speedLabel(speed: Speed): string {
  if (speed === 1) return copy.speed1;
  if (speed === 4) return copy.speed4;
  return copy.speed16;
}

export function RunPage() {
  const params = useParams();
  const runId = params.runId ?? null;
  const [meta, setMeta] = useState<RunSummary | null>(null);
  const [topology, setTopology] = useState<Topology | null>(null);
  const [phase, setPhase] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [replay, setReplay] = useState<boolean | null>(null);
  const [speed, setSpeed] = useState<Speed>(4);
  const [direction, setDirection] = useState<Direction>("LR");
  const [follow, setFollow] = useState(true);
  const [listMode, setListMode] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<"steps" | "node">("steps");
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null);
  const stepsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) return undefined;
    const controller = new AbortController();
    setPhase("loading");
    setReplay(null);
    setMeta(null);
    setTopology(null);
    setArtifacts(null);
    setSelectedId(null);
    setTab("steps");
    listRuns(undefined, 500, controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return null;
        const found = rows.find((row) => row.run_id === runId) ?? null;
        setMeta(found);
        if (!found) {
          setPhase("missing");
          return null;
        }
        setReplay(replayByDefault(found));
        return getTopology(found.graph, controller.signal);
      })
      .then((next) => {
        if (controller.signal.aborted || !next) return;
        setTopology(next);
        setPhase("ready");
      })
      .catch(() => {
        if (!controller.signal.aborted) setPhase("error");
      });
    return () => controller.abort();
  }, [runId]);

  useEffect(() => {
    if (!runId || meta?.graph !== "build") return undefined;
    const controller = new AbortController();
    let active = true;
    Promise.resolve()
      .then(() => getArtifacts(runId, controller.signal))
      .then((next) => {
        if (active) setArtifacts(isArtifacts(next) ? next : null);
      })
      .catch(() => {
        if (active) setArtifacts(null);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [runId, meta?.graph]);

  const stream = useRunEvents(phase === "ready" && replay !== null ? runId : null, {
    replay: replay ?? false,
    speed,
  });
  const view = useMemo(() => fold(stream.events), [stream.events]);
  const shown = stream.events.length > 0 ? view : null;
  const graph = meta?.graph ?? topology?.graph;
  const labelState = shown?.run.state ?? "running";
  const labelStatus = shown?.run.status ?? (stream.events.length === 0 ? meta?.status ?? null : null);
  const elapsed = shown ? shown.run.elapsed_ms : (meta?.elapsed_ms ?? 0);
  const calls = shown ? shown.run.llm_calls : (meta?.llm_calls ?? 0);
  const tokens = shown ? shown.run.tokens_in + shown.run.tokens_out : 0;
  const cost = shown ? shown.run.cost_usd : (meta?.cost_usd ?? null);
  const chipStatus = shown ? runLabel(labelState, labelStatus) : meta ? statusText(meta.status) : copy.emdash;
  const tone = statusTone(shown ? (labelState === "failed" ? "failed" : labelStatus ?? labelState) : meta?.status);

  useEffect(() => {
    const el = stepsRef.current;
    if (!el || tab !== "steps") return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [stream.events.length, tab]);

  const select = (id: string) => {
    setSelectedId(id);
    setTab("node");
  };

  return (
    <div className="page run-page">
      <header className="run-chips">
        <h1 className="run-id">{runId}</h1>
        {meta?.source === "demo" ? <span className="badge">{copy.demo}</span> : null}
        <span className="chip">{graphText(graph)}</span>
        <span className={`chip chip-${tone}`}>{chipStatus}</span>
        <span className="chip">
          <span className="chip-k">{copy.elapsed}</span>
          <span className="mono">{formatElapsed(elapsed)}</span>
        </span>
        <span className="chip">
          <span className="chip-k">{copy.llmCalls}</span>
          <span className="mono">{formatCount(calls)}</span>
        </span>
        <span className="chip">
          <span className="chip-k">{copy.tokens}</span>
          <span className="mono">{formatCount(tokens)}</span>
        </span>
        <span className="chip">
          <span className="chip-k">{copy.cost}</span>
          <span className="mono">{formatCost(cost)}</span>
        </span>
        {replay === null ? null : replay ? (
          <span className="replay-controls">
            <span className="chip">{copy.replay}</span>
            <span className="seg" role="group" aria-label={copy.replay}>
              {SPEEDS.map((value) => (
                <button key={value} type="button" aria-pressed={speed === value} onClick={() => setSpeed(value)}>
                  {speedLabel(value)}
                </button>
              ))}
            </span>
            <button type="button" onClick={stream.restart}>
              {copy.restart}
            </button>
            <button type="button" onClick={() => setReplay(false)}>
              {copy.watchLive}
            </button>
          </span>
        ) : (
          <span className="replay-controls">
            <span className="live-chip">
              <span className="live-dot" aria-hidden="true" />
              {copy.live}
            </span>
            {stream.status === "reconnecting" ? <span className="muted">{copy.reconnecting}</span> : null}
            <button type="button" onClick={() => setReplay(true)}>
              {copy.replay}
            </button>
          </span>
        )}
      </header>
      {phase === "error" ? <p className="empty">{copy.apiDown}</p> : null}
      {phase === "missing" ? <p className="empty">{copy.runMissing}</p> : null}
      {phase !== "error" && phase !== "missing" ? (
        <>
        <div className="run-body">
          <div className="canvas-wrap">
            {topology && replay !== null ? (
              <RunCanvas
                topology={topology}
                view={shown ?? view}
                events={stream.events}
                mode="run"
                direction={direction}
                onDirection={setDirection}
                follow={follow}
                onFollow={setFollow}
                showFollow
                listMode={listMode}
                onListMode={setListMode}
                selectedId={selectedId}
                onSelect={select}
              />
            ) : (
              <p className="empty canvas-loading">{copy.loading}</p>
            )}
          </div>
          <aside className="panel">
            <div className="tabs" role="tablist">
              <button type="button" role="tab" aria-selected={tab === "steps"} onClick={() => setTab("steps")}>
                {copy.tabSteps}
              </button>
              <button type="button" role="tab" aria-selected={tab === "node"} onClick={() => setTab("node")}>
                {copy.tabNode}
              </button>
            </div>
            <div className="panel-body" ref={stepsRef} role="tabpanel">
              {tab === "steps" ? <Steps events={stream.events} /> : <NodeDetail topology={topology} view={shown ?? view} selectedId={selectedId} />}
            </div>
          </aside>
        </div>
        {phase === "ready" && meta ? (
          <ResultPanel key={meta.run_id} graph={meta.graph} view={view} events={stream.events} artifacts={artifacts} />
        ) : null}
        </>
      ) : null}
    </div>
  );
}

function Steps({ events }: { events: RunEvent[] }) {
  if (events.length === 0) return <p className="empty">{copy.noEvents}</p>;
  return (
    <ol className="timeline">
      {events.map((event, index) => (
        <li key={`${event.seq ?? index}`}>
          <span>{formatClock(event.ts)}</span>
          <span className="timeline-text">
            <span>{eventText(event.type)}</span>
            {event.node ? <span>{event.node}</span> : null}
            {event.summary ? <span>{event.summary}</span> : null}
            {event.error_code ? <span>{event.error_code}</span> : null}
            {!event.summary && event.status ? <span>{statusText(event.status)}</span> : null}
          </span>
        </li>
      ))}
    </ol>
  );
}

function NodeDetail({
  topology,
  view,
  selectedId,
}: {
  topology: Topology | null;
  view: RunView;
  selectedId: string | null;
}) {
  const spec = topology?.nodes.find((node) => node.id === selectedId) ?? null;
  if (!spec) return <p className="empty">{copy.selectNode}</p>;
  return <NodeFacts spec={spec} view={view} />;
}

function NodeFacts({ spec, view }: { spec: TopologyNode; view: RunView }) {
  const node = view.nodes[spec.id];
  const state = spec.planned ? "planned" : (node?.state ?? "pending");
  return (
    <dl className="detail">
      <div>
        <dt>{copy.description}</dt>
        <dd className="prose">{spec.description}</dd>
      </div>
      <div>
        <dt>{copy.state}</dt>
        <dd>{stateLabel(state)}</dd>
      </div>
      <div>
        <dt>{copy.attempts}</dt>
        <dd>{node?.attempts ?? 0}</dd>
      </div>
      <div>
        <dt>{copy.duration}</dt>
        <dd>{formatDuration(node?.duration_ms ?? 0)}</dd>
      </div>
      <div>
        <dt>{copy.summary}</dt>
        <dd>{node?.summary ?? copy.none}</dd>
      </div>
      {node?.error_code ? (
        <div>
          <dt>{copy.errorCode}</dt>
          <dd>{node.error_code}</dd>
        </div>
      ) : null}
    </dl>
  );
}
