import type { Artifacts } from "../api/types";
import { copy } from "../copy";
import type { RunView } from "../run/types";
import { summaryTiles } from "./summaryStats";
import { ViewFrame } from "./ViewFrame";

export function SummaryView({ view, artifacts }: { view: RunView | null; artifacts: Artifacts | null }) {
  const tiles = summaryTiles(view, artifacts);
  return (
    <ViewFrame caption={copy.views.summaryCaption} empty={tiles ? null : copy.views.summaryEmpty}>
      <ul className="tiles">
        {tiles?.map((tile) => (
          <li className="tile" key={tile.key}>
            <span className="tile-k">{tile.label}</span>
            <span className="tile-v mono">{tile.value}</span>
          </li>
        ))}
      </ul>
    </ViewFrame>
  );
}
