import { useCallback, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Artifacts } from "../api/types";
import { copy } from "../copy";
import { useTheme } from "../theme";
import { ViewFrame } from "./ViewFrame";

const LAYERS = ["raw", "silver", "gold", "kpi"] as const;
type Layer = (typeof LAYERS)[number];
const NODE_W = 188;
const NODE_H = 48;

interface LineageData extends Record<string, unknown> {
  label: string;
  layer: Layer;
  gap: boolean;
  hot: boolean;
  dim: boolean;
  selected: boolean;
  onSelect: (id: string) => void;
}

type LineageNode = Node<LineageData, "lineage">;

function layerLabel(layer: Layer): string {
  if (layer === "raw") return copy.views.layerRaw;
  if (layer === "silver") return copy.views.layerSilver;
  if (layer === "gold") return copy.views.layerGold;
  return copy.views.layerKpi;
}

function matchesKpi(nodeId: string, kpiId: string): boolean {
  return nodeId === kpiId || nodeId === `kpi_${kpiId}`;
}

function lineageModel(artifacts: Artifacts): { id: string; layer: Layer; gap: boolean }[] {
  const drawn = artifacts.lineage.nodes.filter((node): node is { id: string; layer: Layer } =>
    (LAYERS as readonly string[]).includes(node.layer),
  );
  const nodes = drawn.map((node) => ({
    id: node.id,
    layer: node.layer,
    gap: artifacts.kpis.some((kpi) => kpi.status === "gap" && matchesKpi(node.id, kpi.id)),
  }));
  for (const kpi of artifacts.kpis) {
    if (kpi.status !== "gap") continue;
    if (nodes.some((node) => matchesKpi(node.id, kpi.id))) continue;
    nodes.push({ id: kpi.id, layer: "kpi", gap: true });
  }
  return nodes;
}

function connected(id: string, edges: { source: string; target: string }[]): Set<string> {
  const upstream = new Map<string, string[]>();
  const downstream = new Map<string, string[]>();
  for (const edge of edges) {
    downstream.set(edge.source, [...(downstream.get(edge.source) ?? []), edge.target]);
    upstream.set(edge.target, [...(upstream.get(edge.target) ?? []), edge.source]);
  }
  const seen = new Set<string>([id]);
  const walk = (start: string, graph: Map<string, string[]>) => {
    const stack = [start];
    while (stack.length > 0) {
      const current = stack.pop();
      if (!current) continue;
      for (const next of graph.get(current) ?? []) {
        if (seen.has(next)) continue;
        seen.add(next);
        stack.push(next);
      }
    }
  };
  walk(id, upstream);
  walk(id, downstream);
  return seen;
}

function LineageCard({ data }: NodeProps<LineageNode>) {
  const className = [
    "lineage-node",
    `layer-${data.layer}`,
    data.gap ? "is-gap" : "",
    data.hot ? "is-hot" : "",
    data.dim ? "is-dim" : "",
    data.selected ? "is-selected" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      type="button"
      className={className}
      aria-pressed={data.selected}
      onClick={(event) => {
        event.stopPropagation();
        data.onSelect(data.label);
      }}
    >
      <span className="lineage-id">{data.label}</span>
    </button>
  );
}

const nodeTypes = { lineage: LineageCard };

export function LineageView({ artifacts }: { artifacts: Artifacts | null }) {
  const { theme } = useTheme();
  const [selected, setSelected] = useState<string | null>(null);
  const toggle = useCallback((id: string) => {
    setSelected((current) => (current === id ? null : id));
  }, []);

  const model = useMemo(() => (artifacts ? lineageModel(artifacts) : []), [artifacts]);
  const edges = useMemo(() => artifacts?.lineage.edges ?? [], [artifacts]);
  const hot = useMemo(() => (selected ? connected(selected, edges) : null), [edges, selected]);

  const flowNodes = useMemo<LineageNode[]>(() => {
    return LAYERS.flatMap((layer, column) => {
      const group = model.filter((node) => node.layer === layer).sort((left, right) => left.id.localeCompare(right.id));
      return group.map((node, row) => ({
        id: node.id,
        type: "lineage" as const,
        position: { x: column * (NODE_W + 72), y: row * (NODE_H + 16) },
        width: NODE_W,
        height: NODE_H,
        style: { width: NODE_W, height: NODE_H },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        draggable: false,
        connectable: false,
        data: {
          label: node.id,
          layer: node.layer,
          gap: node.gap,
          hot: hot?.has(node.id) ?? false,
          dim: hot != null && !hot.has(node.id),
          selected: node.id === selected,
          onSelect: toggle,
        },
      }));
    });
  }, [hot, model, selected, toggle]);

  const known = useMemo(() => new Set(model.map((node) => node.id)), [model]);
  const flowEdges = useMemo<Edge[]>(() => {
    return edges
      .filter((edge) => known.has(edge.source) && known.has(edge.target))
      .map((edge, index) => {
        const on = hot != null && hot.has(edge.source) && hot.has(edge.target);
        const dim = hot != null && !on;
        const stroke = on ? "#7c9cff" : theme === "dark" ? "#8b97ad" : "#5c6b82";
        return {
          id: `${edge.source}-${edge.target}-${index}`,
          source: edge.source,
          target: edge.target,
          type: "smoothstep",
          style: { stroke, strokeWidth: on ? 2.2 : 1.4, opacity: dim ? 0.2 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: stroke },
        };
      });
  }, [edges, hot, known, theme]);

  return (
    <ViewFrame caption={copy.views.lineageCaption} empty={model.length === 0 ? copy.views.lineageEmpty : null}>
      <ol className="layer-legend">
        {LAYERS.map((layer) => (
          <li key={layer} className={`layer-key layer-${layer}`}>
            {layerLabel(layer)}
          </li>
        ))}
      </ol>
      <div className="lineage-canvas">
        <div className="canvas-stage">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.16 }}
            minZoom={0.2}
            maxZoom={1.5}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            proOptions={{ hideAttribution: true }}
            colorMode={theme}
            panOnScroll
          >
            <Background variant={BackgroundVariant.Dots} gap={18} size={1.2} color={theme === "dark" ? "#2a3348" : "#c5d0e0"} />
            <Controls showInteractive={false} position="bottom-left" />
          </ReactFlow>
        </div>
      </div>
    </ViewFrame>
  );
}
