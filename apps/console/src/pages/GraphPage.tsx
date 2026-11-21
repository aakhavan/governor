import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { getTopology } from "../api/client";
import type { GraphName, Topology } from "../api/types";
import { copy } from "../copy";
import { RunCanvas } from "../graph/RunCanvas";
import type { Direction } from "../graph/layout";
import { fold } from "../run/fold";

function isGraph(value: string | undefined): value is GraphName {
  return value === "build" || value === "ask";
}

export function GraphPage() {
  const params = useParams();
  const graph = isGraph(params.graph) ? params.graph : null;
  const [topology, setTopology] = useState<Topology | null>(null);
  const [failed, setFailed] = useState(false);
  const [direction, setDirection] = useState<Direction>("LR");
  const [listMode, setListMode] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const emptyView = useMemo(() => fold([]), []);

  useEffect(() => {
    if (!graph) return undefined;
    const controller = new AbortController();
    setTopology(null);
    setFailed(false);
    setSelectedId(null);
    getTopology(graph, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setTopology(next);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [graph]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{graph === "ask" ? copy.navAsk : graph === "build" ? copy.navBuild : copy.unknownGraph}</h1>
          <p className="lead">{graph === "ask" ? copy.askLead : graph === "build" ? copy.buildLead : copy.unknownGraph}</p>
        </div>
      </div>
      {!graph || failed ? <p className="empty">{graph ? copy.apiDown : copy.unknownGraph}</p> : null}
      {graph && !failed ? (
        <div className="canvas-wrap graph-canvas">
          {topology ? (
            <RunCanvas
              topology={topology}
              view={emptyView}
              events={[]}
              mode="topology"
              direction={direction}
              onDirection={setDirection}
              follow={false}
              onFollow={() => {}}
              showFollow={false}
              listMode={listMode}
              onListMode={setListMode}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          ) : (
            <p className="empty canvas-loading">{copy.loading}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
