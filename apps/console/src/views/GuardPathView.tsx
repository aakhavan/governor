import { useMemo } from "react";
import { copy, statusText } from "../copy";
import type { RunEvent, RunView } from "../run/types";
import { guardRows, type CheckId } from "./guardPath";
import { ViewFrame } from "./ViewFrame";

function checkLabel(id: CheckId): string {
  if (id === "guard") return copy.views.checkGuard;
  if (id === "validate") return copy.views.checkValidate;
  if (id === "dry_run") return copy.views.checkDryRun;
  if (id === "execute") return copy.views.checkExecute;
  return copy.views.checkAnswer;
}

export function GuardPathView({ view, events }: { view: RunView | null; events: RunEvent[] }) {
  const rows = useMemo(() => guardRows(events, view), [events, view]);
  return (
    <ViewFrame caption={copy.views.guardCaption} empty={rows ? null : copy.views.guardEmpty}>
      <ol className="waterfall">
        {rows?.map((row, index) => {
          if (row.kind === "repair") {
            return (
              <li key={`repair-${index}`} className="waterfall-step outcome-repair">
                <span className="step-name">{copy.views.repairStep}</span>
                <span className="mono">{row.text || copy.emdash}</span>
              </li>
            );
          }
          if (row.kind === "pending") {
            return (
              <li key={`pending-${row.id}`} className="waterfall-step outcome-pending">
                <span className="step-name">{checkLabel(row.id)}</span>
                <span className="muted">{copy.views.notReached}</span>
              </li>
            );
          }
          return (
            <li key={`${row.id}-${index}`} className={`waterfall-step outcome-${row.outcome}`}>
              <span className="step-name">{checkLabel(row.id)}</span>
              <span className={`chip chip-${row.outcome === "pass" ? "ok" : "bad"}`}>
                {statusText(row.outcome === "pass" ? "pass" : "refused")}
              </span>
              {row.code ? <span className="mono step-code">{row.code}</span> : null}
            </li>
          );
        })}
      </ol>
    </ViewFrame>
  );
}
