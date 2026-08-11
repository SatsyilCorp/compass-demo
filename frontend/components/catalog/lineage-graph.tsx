"use client";

import { useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { X, FileJson, Layers, Database, BrainCircuit, LayoutDashboard, type LucideIcon } from "lucide-react";
import type { LineageEdge, LineageNode } from "@/lib/types";

type LineageKind = LineageNode["kind"];

type FlowNodeData = {
  label: string;
  kind: LineageKind;
  nodeId: string;
  meta?: Record<string, unknown>;
};
type FlowLineageNode = Node<FlowNodeData, "lineage">;

const KIND_META: Record<LineageKind, { label: string; icon: LucideIcon; border: string; chipBg: string; chipText: string }> = {
  source: { label: "Source", icon: FileJson, border: "border-border-strong", chipBg: "bg-surface-2", chipText: "text-text-muted" },
  stage: { label: "Stage", icon: Layers, border: "border-gold", chipBg: "bg-gold-soft", chipText: "text-gold-ink" },
  table: { label: "Table", icon: Database, border: "border-gov-primary", chipBg: "bg-accent-soft", chipText: "text-gov-primary" },
  model: { label: "Model", icon: BrainCircuit, border: "border-[#4a3aa7]", chipBg: "bg-[#4a3aa7]/10", chipText: "text-[#4a3aa7]" },
  dashboard: { label: "Dashboard", icon: LayoutDashboard, border: "border-success", chipBg: "bg-success-soft", chipText: "text-success" },
};

function LineageFlowNode({ data, selected }: NodeProps<FlowLineageNode>) {
  const meta = KIND_META[data.kind];
  const Icon = meta.icon;
  return (
    <div
      className={`w-[220px] rounded-lg border-2 bg-surface p-3 shadow-card transition-shadow ${meta.border} ${
        selected ? "ring-2 ring-gold ring-offset-2 ring-offset-bg" : ""
      }`}
    >
      <Handle type="target" position={Position.Left} className="!bg-border-strong" />
      <div className="flex items-start gap-2">
        <span className={`inline-flex size-7 shrink-0 items-center justify-center rounded ${meta.chipBg} ${meta.chipText}`}>
          <Icon className="size-3.5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className={`text-[10px] font-semibold uppercase tracking-[0.1em] ${meta.chipText}`}>{meta.label}</p>
          <p className="mt-0.5 truncate text-[12.5px] font-semibold leading-snug text-text-strong" title={data.label}>
            {data.label}
          </p>
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-border-strong" />
    </div>
  );
}

// `NodeTypes` values are typed `ComponentType<NodeProps & { data: any }>` by
// @xyflow/react itself, so our narrower `NodeProps<FlowLineageNode>` fits
// without a cast.
const nodeTypes: NodeTypes = { lineage: LineageFlowNode };

/** Longest-path layered layout (source → … → dashboard), left to right. */
function layout(nodes: LineageNode[], edges: LineageEdge[]) {
  const outgoing = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  for (const n of nodes) {
    outgoing.set(n.node_id, []);
    indegree.set(n.node_id, 0);
  }
  for (const e of edges) {
    outgoing.get(e.from_node)?.push(e.to_node);
    indegree.set(e.to_node, (indegree.get(e.to_node) ?? 0) + 1);
  }

  const depth = new Map<string, number>();
  const queue: string[] = [];
  for (const n of nodes) {
    if ((indegree.get(n.node_id) ?? 0) === 0) {
      depth.set(n.node_id, 0);
      queue.push(n.node_id);
    }
  }
  const remaining = new Map(indegree);
  while (queue.length > 0) {
    const id = queue.shift()!;
    const d = depth.get(id) ?? 0;
    for (const next of outgoing.get(id) ?? []) {
      depth.set(next, Math.max(depth.get(next) ?? 0, d + 1));
      const left = (remaining.get(next) ?? 0) - 1;
      remaining.set(next, left);
      if (left === 0) queue.push(next);
    }
  }

  const byDepth = new Map<number, string[]>();
  for (const n of nodes) {
    const d = depth.get(n.node_id) ?? 0;
    if (!byDepth.has(d)) byDepth.set(d, []);
    byDepth.get(d)!.push(n.node_id);
  }

  const COL_W = 280;
  const ROW_H = 130;
  const positions = new Map<string, { x: number; y: number }>();
  for (const [d, ids] of byDepth) {
    ids.forEach((id, i) => {
      const yOffset = (i - (ids.length - 1) / 2) * ROW_H;
      positions.set(id, { x: d * COL_W, y: yOffset + 280 });
    });
  }
  return positions;
}

export function LineageGraph({ nodes: rawNodes, edges: rawEdges }: { nodes: LineageNode[]; edges: LineageEdge[] }) {
  const [selected, setSelected] = useState<LineageNode | null>(null);

  const positions = useMemo(() => layout(rawNodes, rawEdges), [rawNodes, rawEdges]);

  const flowNodes: FlowLineageNode[] = useMemo(
    () =>
      rawNodes.map((n) => ({
        id: n.node_id,
        type: "lineage",
        position: positions.get(n.node_id) ?? { x: 0, y: 0 },
        data: { label: n.label, kind: n.kind, nodeId: n.node_id, meta: n.meta },
      })),
    [rawNodes, positions],
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      rawEdges.map((e) => ({
        id: `${e.from_node}->${e.to_node}`,
        source: e.from_node,
        target: e.to_node,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed, color: "var(--color-border-strong)" },
        style: { stroke: "var(--color-border-strong)", strokeWidth: 1.75 },
      })),
    [rawEdges],
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
      <div className="h-[560px] overflow-hidden rounded-md border border-border bg-surface">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => {
            const found = rawNodes.find((n) => n.node_id === node.id) ?? null;
            setSelected(found);
          }}
          onPaneClick={() => setSelected(null)}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.4}
          maxZoom={1.5}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--color-border)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <aside className="rounded-md border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-subtle">Node detail</p>
          {selected && (
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="rounded p-0.5 text-text-subtle hover:bg-surface-2 hover:text-text"
              aria-label="Close node detail"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>

        {!selected ? (
          <>
            <p className="text-xs leading-relaxed text-text-muted">
              Click any node in the graph to inspect its metadata - this is the same DAG the ingest and analysis
              pipeline emits into <code className="font-mono text-[11px]">lineage_nodes</code> /{" "}
              <code className="font-mono text-[11px]">lineage_edges</code> for this run.
            </p>
            <Legend />
          </>
        ) : (
          <div className="space-y-3 text-xs">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-text-subtle">
                {KIND_META[selected.kind].label}
              </p>
              <p className="mt-0.5 text-sm font-semibold text-text-strong">{selected.label}</p>
            </div>
            <dl className="space-y-1.5">
              <Row label="node_id" value={selected.node_id} mono />
              <Row label="run_id" value={selected.run_id} mono />
              {selected.meta &&
                Object.entries(selected.meta).map(([k, v]) => (
                  <Row key={k} label={k} value={typeof v === "object" ? JSON.stringify(v) : String(v)} mono />
                ))}
            </dl>
          </div>
        )}
      </aside>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 border-t border-border-2 pt-1.5 first:border-0 first:pt-0">
      <dt className="shrink-0 text-text-subtle">{label}</dt>
      <dd className={`text-right text-text ${mono ? "font-mono text-[11px]" : ""}`}>{value}</dd>
    </div>
  );
}

function Legend() {
  return (
    <ul className="mt-4 space-y-1.5">
      {(Object.keys(KIND_META) as LineageKind[]).map((kind) => {
        const meta = KIND_META[kind];
        const Icon = meta.icon;
        return (
          <li key={kind} className="flex items-center gap-2 text-[11px] text-text-muted">
            <span className={`inline-flex size-5 items-center justify-center rounded ${meta.chipBg} ${meta.chipText}`}>
              <Icon className="size-3" aria-hidden />
            </span>
            {meta.label}
          </li>
        );
      })}
    </ul>
  );
}
