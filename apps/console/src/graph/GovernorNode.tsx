import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { attemptBadge } from "../copy";
import { formatDuration } from "../run/format";
import { DoneMark, KindIcon } from "./icons";
import { nodeClass, nodeLabel, nodeStatusText, nodeStyle, type GovernorData } from "./nodeState";

export type GovernorFlowNode = Node<GovernorData, "governor">;

export function GovernorCard({ data, selected, labelled = true }: { data: GovernorData; selected: boolean; labelled?: boolean }) {
  const status = nodeStatusText(data);
  const duration = data.durationMs > 0 ? formatDuration(data.durationMs) : "";
  return (
    <div
      className={nodeClass(data, selected)}
      style={nodeStyle(data)}
      title={data.description}
      aria-label={labelled ? nodeLabel(data) : undefined}
      aria-hidden={labelled ? undefined : true}
    >
      {data.attempts > 1 ? <span className="node-badge">{attemptBadge(data.attempts)}</span> : null}
      <KindIcon kind={data.kind} />
      <div className="node-body">
        <div className="node-label">{data.label}</div>
        <div className="node-status">
          {data.state === "done" ? <DoneMark /> : null}
          <span className="node-status-text">{status}</span>
          {duration ? <span className="node-duration">{duration}</span> : null}
        </div>
      </div>
    </div>
  );
}

export function GovernorNode({ data, selected, sourcePosition, targetPosition }: NodeProps<GovernorFlowNode>) {
  return (
    <>
      <Handle type="target" position={targetPosition ?? Position.Left} isConnectable={false} />
      <GovernorCard data={data} selected={Boolean(selected)} />
      <Handle type="source" position={sourcePosition ?? Position.Right} isConnectable={false} />
    </>
  );
}
