import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns } from "../api/client";
import type { RunSummary } from "../api/types";
import { copy, graphText, statusText } from "../copy";
import { formatCost, formatElapsed, formatStamp, statusTone } from "../run/format";

export function RunsPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setFailed(false);
    listRuns(undefined, 500, controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) setRuns(rows);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [tick]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{copy.runsTitle}</h1>
          <p className="lead">{copy.runsLead}</p>
        </div>
        <button type="button" onClick={() => setTick((value) => value + 1)}>
          {copy.refresh}
        </button>
      </div>
      {failed ? <p className="empty">{copy.apiDown}</p> : null}
      {!failed && runs === null ? <p className="empty">{copy.loading}</p> : null}
      {!failed && runs && runs.length === 0 ? <p className="empty">{copy.noRuns}</p> : null}
      {!failed && runs && runs.length > 0 ? (
        <div className="table-wrap">
          <table className="runs">
            <thead>
              <tr>
                <th>{copy.colRun}</th>
                <th>{copy.colGraph}</th>
                <th>{copy.colStarted}</th>
                <th>{copy.colStatus}</th>
                <th>{copy.colElapsed}</th>
                <th>{copy.colCost}</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={`${run.graph}:${run.run_id}`}
                  tabIndex={0}
                  onClick={() => navigate(`/runs/${encodeURIComponent(run.run_id)}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      navigate(`/runs/${encodeURIComponent(run.run_id)}`);
                    }
                  }}
                >
                  <td>
                    <span className="mono">{run.run_id}</span>
                    {run.source === "demo" ? <span className="badge">{copy.demo}</span> : null}
                  </td>
                  <td>{graphText(run.graph)}</td>
                  <td className="mono">{formatStamp(run.started)}</td>
                  <td>
                    <span className={`chip chip-${statusTone(run.status)}`}>{statusText(run.status)}</span>
                  </td>
                  <td className="mono">{formatElapsed(run.elapsed_ms)}</td>
                  <td className="mono">{formatCost(run.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
