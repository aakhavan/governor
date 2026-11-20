import { Bar, BarChart, XAxis, YAxis } from "recharts";
import type { Artifacts } from "../api/types";
import { copy } from "../copy";
import { formatCount } from "../run/format";
import { useBoxWidth } from "./useBoxWidth";
import { ViewFrame } from "./ViewFrame";

const STAGES = ["requested", "computable", "proposed", "validated", "built"] as const;

interface Stage {
  key: string;
  label: string;
  value: number | null;
}

function stageLabel(key: (typeof STAGES)[number]): string {
  if (key === "requested") return copy.views.requested;
  if (key === "computable") return copy.views.computable;
  if (key === "proposed") return copy.views.proposed;
  if (key === "validated") return copy.views.validated;
  return copy.views.built;
}

function Bars({ rows, color }: { rows: Stage[]; color: string }) {
  const { ref, width } = useBoxWidth(560);
  const height = Math.max(160, rows.length * 36 + 16);
  const data = rows.map((row) => ({ label: row.label, value: row.value ?? 0 }));
  return (
    <div className="chart-row" ref={ref}>
      <ul className="stage-readout">
        {rows.map((row) => (
          <li key={row.key}>
            <span>{row.label}</span>
            <span className="mono">{row.value == null ? copy.emdash : formatCount(row.value)}</span>
          </li>
        ))}
      </ul>
      <BarChart
        width={Math.max(240, width - 188)}
        height={height}
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
      >
        <XAxis type="number" allowDecimals={false} tick={{ fill: "currentColor", fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="label" hide />
        <Bar dataKey="value" fill={color} barSize={14} radius={[0, 6, 6, 0]} isAnimationActive={false} />
      </BarChart>
    </div>
  );
}

export function FunnelView({ artifacts }: { artifacts: Artifacts | null }) {
  const stages: Stage[] = STAGES.map((key) => ({
    key,
    label: stageLabel(key),
    value: artifacts ? artifacts.funnel[key] : null,
  }));
  const ready = stages.some((stage) => stage.value != null);
  const findings = Object.entries(artifacts?.finding_codes ?? {}).sort((left, right) => {
    if (right[1] !== left[1]) return right[1] - left[1];
    return left[0].localeCompare(right[0]);
  });
  return (
    <ViewFrame caption={copy.views.funnelCaption} empty={ready ? null : copy.views.funnelEmpty}>
      <Bars rows={stages} color="#5b7fd6" />
      <h3 className="chart-title">{copy.views.funnelStopped}</h3>
      {findings.length === 0 ? (
        <p className="empty">{copy.views.funnelClear}</p>
      ) : (
        <Bars
          rows={findings.map(([code, count]) => ({ key: code, label: code, value: count }))}
          color="#c44752"
        />
      )}
    </ViewFrame>
  );
}
