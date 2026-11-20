import { useState } from "react";
import type { Artifacts, GraphName } from "../api/types";
import { copy } from "../copy";
import type { RunEvent, RunView } from "../run/types";
import { FunnelView } from "./FunnelView";
import { GuardPathView } from "./GuardPathView";
import { KpiEvidenceView } from "./KpiEvidenceView";
import { LineageView } from "./LineageView";
import { SummaryView } from "./SummaryView";

const BUILD_TABS = ["summary", "lineage", "funnel", "kpi"] as const;
const ASK_TABS = ["guard"] as const;
type ResultTab = (typeof BUILD_TABS)[number] | (typeof ASK_TABS)[number];

function tabLabel(tab: ResultTab): string {
  if (tab === "summary") return copy.views.tabSummary;
  if (tab === "lineage") return copy.views.tabLineage;
  if (tab === "funnel") return copy.views.tabFunnel;
  if (tab === "kpi") return copy.views.tabKpi;
  return copy.views.tabGuard;
}

export function ResultPanel({
  graph,
  view,
  events,
  artifacts,
}: {
  graph: GraphName;
  view: RunView;
  events: RunEvent[];
  artifacts: Artifacts | null;
}) {
  const [tab, setTab] = useState<ResultTab>(graph === "ask" ? "guard" : "summary");
  const tabs = graph === "ask" ? ASK_TABS : BUILD_TABS;
  const active = (tabs as readonly string[]).includes(tab) ? tab : tabs[0];
  return (
    <section className="result-views">
      <div className="tabs" role="tablist" aria-label={copy.views.results}>
        {tabs.map((item) => (
          <button key={item} type="button" role="tab" aria-selected={active === item} onClick={() => setTab(item)}>
            {tabLabel(item)}
          </button>
        ))}
      </div>
      <div className="result-body" role="tabpanel">
        {active === "summary" ? <SummaryView view={view} artifacts={artifacts} /> : null}
        {active === "lineage" ? <LineageView artifacts={artifacts} /> : null}
        {active === "funnel" ? <FunnelView artifacts={artifacts} /> : null}
        {active === "kpi" ? <KpiEvidenceView artifacts={artifacts} /> : null}
        {active === "guard" ? <GuardPathView view={view} events={events} /> : null}
      </div>
    </section>
  );
}
