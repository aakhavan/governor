import { Cell, Pie, PieChart } from "recharts";
import type { Artifacts } from "../api/types";
import { copy, statusText } from "../copy";
import { formatCount } from "../run/format";
import { ViewFrame } from "./ViewFrame";

const SLICES = [
  { key: "built", fill: "#1f9d73" },
  { key: "gap", fill: "#c4841d" },
  { key: "declined", fill: "#c44752" },
] as const;

export function KpiEvidenceView({ artifacts }: { artifacts: Artifacts | null }) {
  const kpis = artifacts?.kpis ?? [];
  const counts = {
    built: kpis.filter((kpi) => kpi.status === "built").length,
    gap: kpis.filter((kpi) => kpi.status === "gap").length,
    declined: kpis.filter((kpi) => kpi.status === "declined").length,
  };
  const slices = SLICES.filter((slice) => counts[slice.key] > 0).map((slice) => ({
    ...slice,
    label: statusText(slice.key),
    value: counts[slice.key],
  }));
  const tests = artifacts?.tests_passed;
  return (
    <ViewFrame caption={copy.views.kpiCaption} empty={kpis.length === 0 ? copy.views.kpiEmpty : null}>
      <div className="evidence">
        <div className="donut">
          <PieChart width={220} height={200}>
            <Pie data={slices} dataKey="value" nameKey="label" innerRadius={56} outerRadius={82} isAnimationActive={false} stroke="none">
              {slices.map((slice) => (
                <Cell key={slice.key} fill={slice.fill} />
              ))}
            </Pie>
          </PieChart>
          <ul className="legend">
            {SLICES.map((slice) => (
              <li key={slice.key}>
                <span className="swatch" style={{ background: slice.fill }} />
                <span>{statusText(slice.key)}</span>
                <span className="mono">{formatCount(counts[slice.key])}</span>
              </li>
            ))}
          </ul>
        </div>
        <ul className="kpi-grid">
          {kpis.map((kpi) => (
            <li key={kpi.id} className={`kpi-card kpi-${kpi.status}`}>
              <h3 className="kpi-id">{kpi.id}</h3>
              <p className={`chip chip-${kpi.status === "built" ? "ok" : kpi.status === "gap" ? "warn" : "bad"}`}>
                {statusText(kpi.status)}
              </p>
              <p className="tile-k">{copy.views.models}</p>
              {kpi.models.length === 0 ? (
                <p className="empty">{copy.views.noModels}</p>
              ) : (
                <ul className="model-list">
                  {kpi.models.map((name) => (
                    <li key={name} className="mono">
                      {name}
                    </li>
                  ))}
                </ul>
              )}
              <p className="tile-k">{copy.views.tests}</p>
              <p className="mono">{tests == null ? copy.emdash : formatCount(tests)}</p>
            </li>
          ))}
        </ul>
      </div>
    </ViewFrame>
  );
}
