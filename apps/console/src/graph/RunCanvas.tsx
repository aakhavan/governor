import { Component, useEffect, useMemo, type CSSProperties, type ReactNode } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  Position,
  ReactFlow,
  useReactFlow,
  type Edge,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Topology, TopologyNode } from "../api/types";
import { copy } from "../copy";
import type { RunEvent, RunView } from "../run/types";
import { useTheme } from "../theme";
import { classifyEdges, pairKey, type EdgeVisual, type PillData } from "./edges";
import { GovernorCard, GovernorNode, type GovernorFlowNode } from "./GovernorNode";
import { NODE_HEIGHT, NODE_WIDTH, placeNodes, type Direction } from "./layout";
import { nodeLabel, type GovernorData } from "./nodeState";
import { PillEdge } from "./PillEdge";

const nodeTypes = { governor: GovernorNode };
const edgeTypes = { pill: PillEdge };

interface BoundaryState {
  failed: boolean;
}

class CanvasBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return <p className="empty">{copy.canvasError}</p>;
    return this.props.children;
  }
}

function edgePaint(state: EdgeVisual, theme: "dark" | "light"): CSSProperties {
  if (state === "active") return { stroke: "#7c9cff", strokeWidth: 2.4 };
  if (state === "traversed") return { stroke: theme === "dark" ? "#d5ddee" : "#243044", strokeWidth: 2 };
  if (state === "map") return { stroke: theme === "dark" ? "#8b97ad" : "#5c6b82", strokeWidth: 1.6 };
  return { stroke: theme === "dark" ? "#3a4254" : "#c5cedd", strokeWidth: 1.25 };
}

function FollowLive({ enabled, x, y }: { enabled: boolean; x: number | null; y: number | null }) {
  const { setCenter } = useReactFlow();
  useEffect(() => {
    if (!enabled || x == null || y == null) return;
    void setCenter(x + NODE_WIDTH / 2, y + NODE_HEIGHT / 2, { duration: 480 });
  }, [enabled, x, y, setCenter]);
  return null;
}

export interface RunCanvasProps {
  topology: Topology;
  view: RunView;
  events: RunEvent[];
  mode: "run" | "topology";
  direction: Direction;
  onDirection: (direction: Direction) => void;
  follow: boolean;
  onFollow: (follow: boolean) => void;
  showFollow: boolean;
  listMode: boolean;
  onListMode: (listMode: boolean) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function RunCanvas(props: RunCanvasProps) {
  const { theme } = useTheme();
  const ordered = useMemo(
    () => [...props.topology.nodes].sort((left, right) => left.order - right.order || left.id.localeCompare(right.id)),
    [props.topology.nodes],
  );
  const positions = useMemo(
    () => placeNodes(ordered.map((node) => node.id), props.topology.edges, props.direction),
    [ordered, props.topology.edges, props.direction],
  );

  const dataFor = (spec: TopologyNode): GovernorData => {
    const node = props.view.nodes[spec.id];
    return {
      label: spec.label,
      kind: spec.kind,
      description: spec.description,
      group: spec.group,
      state: spec.planned ? "planned" : (node?.state ?? "pending"),
      attempts: node?.attempts ?? 0,
      durationMs: node?.duration_ms ?? 0,
      summary: node?.summary ?? null,
      errorCode: node?.error_code ?? null,
      pauseStatus: props.view.run.status,
      mode: props.mode,
    };
  };

  const flowNodes = useMemo<GovernorFlowNode[]>(() => {
    return ordered.map((spec) => ({
      id: spec.id,
      type: "governor",
      position: positions.get(spec.id) ?? { x: 0, y: 0 },
      sourcePosition: props.direction === "TB" ? Position.Bottom : Position.Right,
      targetPosition: props.direction === "TB" ? Position.Top : Position.Left,
      draggable: false,
      connectable: false,
      selected: spec.id === props.selectedId,
      data: {
        label: spec.label,
        kind: spec.kind,
        description: spec.description,
        group: spec.group,
        state: spec.planned ? "planned" : (props.view.nodes[spec.id]?.state ?? "pending"),
        attempts: props.view.nodes[spec.id]?.attempts ?? 0,
        durationMs: props.view.nodes[spec.id]?.duration_ms ?? 0,
        summary: props.view.nodes[spec.id]?.summary ?? null,
        errorCode: props.view.nodes[spec.id]?.error_code ?? null,
        pauseStatus: props.view.run.status,
        mode: props.mode,
      },
    }));
  }, [ordered, positions, props.direction, props.mode, props.selectedId, props.view]);

  const visuals = useMemo(
    () => classifyEdges(props.events, props.view.run.current_node),
    [props.events, props.view.run.current_node],
  );

  const flowEdges = useMemo<Edge<PillData>[]>(() => {
    return props.topology.edges.map((edge, index) => {
      const key = pairKey(edge.source, edge.target);
      const state: EdgeVisual =
        props.mode === "topology"
          ? "map"
          : visuals.active === key
            ? "active"
            : visuals.traversed.has(key)
              ? "traversed"
              : "dim";
      const paint = edgePaint(state, theme);
      const stroke = typeof paint.stroke === "string" ? paint.stroke : "#8b97ad";
      return {
        id: `${edge.source}-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        type: "pill",
        label: edge.conditional && edge.label ? edge.label : undefined,
        animated: state === "active",
        style: paint,
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: stroke },
        data: { state },
      };
    });
  }, [props.mode, props.topology.edges, theme, visuals]);

  const onNodeClick: NodeMouseHandler<GovernorFlowNode> = (_event, node) => props.onSelect(node.id);
  const current = props.view.run.current_node ? positions.get(props.view.run.current_node) : undefined;

  return (
    <div className="canvas-frame">
      <div className="canvas-toolbar">
        <div className="seg" role="group" aria-label={copy.leftToRight}>
          <button type="button" aria-pressed={props.direction === "LR"} onClick={() => props.onDirection("LR")}>
            {copy.leftToRight}
          </button>
          <button type="button" aria-pressed={props.direction === "TB"} onClick={() => props.onDirection("TB")}>
            {copy.topToBottom}
          </button>
        </div>
        {props.showFollow ? (
          <button type="button" aria-pressed={props.follow} onClick={() => props.onFollow(!props.follow)}>
            {copy.followLive}
          </button>
        ) : null}
        <button type="button" aria-pressed={props.listMode} onClick={() => props.onListMode(!props.listMode)}>
          {props.listMode ? copy.showCanvas : copy.showList}
        </button>
      </div>
      {props.listMode ? (
        <ol className="node-list">
          {ordered.map((spec) => {
            const data = dataFor(spec);
            return (
              <li key={spec.id}>
                <button type="button" className="node-list-btn" aria-label={nodeLabel(data)} onClick={() => props.onSelect(spec.id)}>
                  <GovernorCard data={data} selected={spec.id === props.selectedId} labelled={false} />
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="canvas-stage">
          <CanvasBoundary>
            <ReactFlow
              key={props.direction}
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodeClick={onNodeClick}
              fitView
              fitViewOptions={{ padding: 0.18 }}
              minZoom={0.15}
              maxZoom={1.6}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              proOptions={{ hideAttribution: true }}
              colorMode={theme}
              panOnScroll
            >
              <FollowLive enabled={props.follow} x={current?.x ?? null} y={current?.y ?? null} />
              <Background variant={BackgroundVariant.Dots} gap={18} size={1.2} color={theme === "dark" ? "#2a3348" : "#c5d0e0"} />
              <Controls showInteractive={false} position="bottom-left" />
            </ReactFlow>
          </CanvasBoundary>
        </div>
      )}
    </div>
  );
}
