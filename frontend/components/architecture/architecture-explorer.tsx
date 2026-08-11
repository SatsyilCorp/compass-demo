"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  ArrowRight,
  Boxes,
  CheckCircle2,
  CircleDollarSign,
  Database,
  ExternalLink,
  Gauge,
  Layers3,
  Network,
  Pause,
  Play,
  Search,
  ShieldCheck,
  UsersRound,
  X,
} from "lucide-react";

import {
  ARCHITECTURE_VIEWS,
  COMPONENTS,
  FLOW_META,
  PLANE_META,
  SCALE_PROFILES,
  SCALE_STAGES,
  componentsForView,
  connectionsForView,
  type ArchitectureComponent,
  type ArchitecturePlane,
  type ArchitectureView,
  type ScaleProfile,
} from "./model";

type DiagramNodeData = {
  component: ArchitectureComponent;
  active: boolean;
  searchMatch: boolean;
  profileBadge: string | null;
};

type DiagramNode = Node<DiagramNodeData, "architecture">;

const SCALE_NODE_STAGE: Record<string, number> = {
  personas: 1,
  cognito: 1,
  "http-api": 1,
  "scale-control": 2,
  "scale-ledger": 2,
  "scale-workflow": 3,
  "worker-queue": 4,
  "worker-dlq": 4,
  "scale-worker": 5,
  "scale-lake": 6,
  glue: 7,
  "lake-formation": 7,
  athena: 7,
  "export-queue": 9,
  "export-dlq": 9,
  "scale-export": 9,
};

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4, maximumFractionDigits: 4 });

const DEPLOYMENT_META: Record<ArchitectureComponent["deployment"], { label: string; className: string }> = {
  core: { label: "Deployed core", className: "border-success/30 bg-success-soft text-success" },
  scale: { label: "Deployed scale", className: "border-gov-primary/25 bg-gov-primary-lighter text-gov-primary" },
  conditional: { label: "Conditional service", className: "border-gold/40 bg-gold-soft text-gold-ink" },
  logical: { label: "Logical boundary", className: "border-border bg-surface-2 text-text-subtle" },
};

function ArchitectureFlowNode({ data, selected }: NodeProps<DiagramNode>) {
  const { component, active, searchMatch, profileBadge } = data;
  const plane = PLANE_META[component.plane];
  const deployment = DEPLOYMENT_META[component.deployment];
  return (
    <div
      className={`group relative w-[210px] rounded-xl border-2 bg-white p-3 shadow-card transition-all ${
        selected ? "ring-4 ring-gold-light/45" : ""
      } ${active ? "opacity-100" : "opacity-38 grayscale"} ${searchMatch ? "" : "opacity-25"}`}
      style={{ borderColor: plane.color }}
      aria-label={`${component.label}, ${component.service}`}
    >
      <Handle type="target" position={Position.Left} className="!size-2.5 !border-2 !border-white" style={{ background: plane.color }} />
      <div className="flex items-start gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-lg border border-border bg-surface-2">
          {component.icon ? (
            <img src={component.icon} alt="" className="size-8 object-contain" />
          ) : (
            <UsersRound className="size-6 text-gov-primary" aria-hidden />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[9px] font-bold uppercase tracking-[0.13em]" style={{ color: plane.color }}>
            {plane.label}
          </span>
          <span className="mt-0.5 block text-[12.5px] font-bold leading-4 text-text-strong">{component.label}</span>
          <span className="mt-1 block text-[9.5px] leading-3.5 text-text-muted">{component.service}</span>
        </span>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border-2 pt-2">
        <span className={`rounded-full border px-2 py-0.5 text-[8.5px] font-bold uppercase tracking-wide ${deployment.className}`}>
          {deployment.label}
        </span>
        {profileBadge ? <span className="font-mono text-[9px] font-bold text-gov-primary">{profileBadge}</span> : null}
      </div>
      <Handle type="source" position={Position.Right} className="!size-2.5 !border-2 !border-white" style={{ background: plane.color }} />
    </div>
  );
}

const nodeTypes: NodeTypes = { architecture: ArchitectureFlowNode };

export function ArchitectureExplorer() {
  const [view, setView] = useState<ArchitectureView>("platform");
  const [profileId, setProfileId] = useState<ScaleProfile["id"]>("1m");
  const [scaleStage, setScaleStage] = useState(9);
  const [playing, setPlaying] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string>("cloudfront");

  const profile = SCALE_PROFILES.find((candidate) => candidate.id === profileId) ?? SCALE_PROFILES[3];
  const viewComponents = useMemo(() => componentsForView(view), [view]);
  const viewConnections = useMemo(() => connectionsForView(view), [view]);

  useEffect(() => {
    const selectedVisible = viewComponents.some((component) => component.id === selectedId);
    if (!selectedVisible) setSelectedId(viewComponents[0]?.id ?? "personas");
  }, [selectedId, viewComponents]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setScaleStage((current) => {
        if (current >= SCALE_STAGES.length) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 1_150);
    return () => window.clearInterval(timer);
  }, [playing]);

  const normalizedQuery = query.trim().toLowerCase();
  const nodes: DiagramNode[] = useMemo(
    () => viewComponents.map((component) => {
      const requiredStage = SCALE_NODE_STAGE[component.id] ?? 1;
      const active = view !== "scale" || requiredStage <= scaleStage;
      const searchMatch = !normalizedQuery || [component.label, component.service, component.summary, component.plane]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
      return {
        id: component.id,
        type: "architecture",
        position: component.positions[view]!,
        data: { component, active, searchMatch, profileBadge: badgeFor(component.id, profile) },
        selected: selectedId === component.id,
      };
    }),
    [normalizedQuery, profile, scaleStage, selectedId, view, viewComponents],
  );

  const edges: Edge[] = useMemo(
    () => viewConnections.map((connection) => {
      const meta = FLOW_META[connection.kind];
      const active = view !== "scale" || (connection.scaleStage ?? 1) <= scaleStage;
      return {
        id: connection.id,
        source: connection.source,
        target: connection.target,
        type: "smoothstep",
        animated: active && (view === "scale" || connection.kind === "data"),
        label: connection.label,
        markerEnd: { type: MarkerType.ArrowClosed, color: meta.color, width: 16, height: 16 },
        style: {
          stroke: meta.color,
          strokeWidth: active ? 2.2 : 1.2,
          strokeDasharray: meta.dash,
          opacity: active ? 0.88 : 0.16,
        },
        labelStyle: { fill: "#334155", fontSize: 9, fontWeight: 700 },
        labelBgStyle: { fill: "#ffffff", fillOpacity: 0.9 },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 4,
      };
    }),
    [scaleStage, view, viewConnections],
  );

  const selected = COMPONENTS.find((component) => component.id === selectedId) ?? null;
  const inventoryMatches = COMPONENTS.filter((component) => !normalizedQuery || [component.label, component.service, component.summary, component.plane]
    .join(" ")
    .toLowerCase()
    .includes(normalizedQuery));

  const selectView = (next: ArchitectureView) => {
    setView(next);
    setPlaying(false);
    if (next === "scale") setScaleStage(9);
  };

  const playFlow = () => {
    if (scaleStage >= SCALE_STAGES.length) setScaleStage(1);
    setPlaying(true);
  };

  return (
    <div className="mt-6 space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card" aria-label="Architecture scope statement">
        <div className="grid gap-5 px-5 py-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)] lg:px-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-gold-light">Architecture truth</p>
            <h2 className="mt-2 text-xl font-bold">Deployed AWS-native proving prototype</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/72">
              The core mission path and bounded scale path are deployed in Satsyil AWS. Conditional security services and logical boundaries are labeled separately so the diagram does not imply deployment where none is proven.
            </p>
          </div>
          <div className="rounded-lg border border-white/15 bg-white/[0.07] p-4">
            <p className="text-xs font-bold text-gold-light">Production boundary</p>
            <p className="mt-1 text-[11px] leading-5 text-white/70">
              This is not a FedRAMP High, IL5, ATO, or Government production authorization. Scale evidence is synthetic and bounded from 1K through 1M records.
            </p>
          </div>
        </div>
        <div className="grid border-t border-white/12 bg-black/10 md:grid-cols-3">
          <FlowSummary color="#7dd3fc" label="Control flow" text="Cognito to API Gateway to Step Functions, queues, and durable run state." />
          <FlowSummary color="#86efac" label="Data flow" text="S3, Aurora, Kinesis, Glue, Lake Formation, Athena, and governed exports." />
          <FlowSummary color="#fde68a" label="Evidence flow" text="Quality, lineage, audit, cost, stage, alarm, and checksummed release receipts." />
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6" aria-label="Deployed architecture facts">
        <Fact icon={Activity} value="25" label="protected operations" detail="23 URL paths" />
        <Fact icon={Boxes} value="17" label="Lambda functions" detail="14 mission and 3 scale" />
        <Fact icon={Network} value="2" label="durable workflows" detail="Express intake and Standard scale" />
        <Fact icon={Database} value="6" label="lake datasets" detail="JSON Lines and Parquet" />
        <Fact icon={ShieldCheck} value="11" label="health alarms" detail="all critical seams" />
        <Fact icon={Layers3} value="2 AZ" label="HA database" detail="private writer and reader" />
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
        <div className="border-b border-border bg-white px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">Interactive deployed topology</p>
              <h2 className="mt-1 text-lg font-bold text-text-strong">Select a view, follow a flow, then inspect any box</h2>
              <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">
                Every box is labeled as deployed core, deployed scale, conditional service, or logical boundary. Select one to see its interface, scaling, recovery, security, and retained evidence contract.
              </p>
            </div>
            <label className="relative block w-full max-w-sm">
              <span className="sr-only">Search architecture</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-subtle" aria-hidden />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Find a service, role, or control"
                className="min-h-11 w-full rounded-md border border-border bg-white pl-10 pr-10 text-sm text-text-strong outline-none placeholder:text-text-subtle focus:border-gov-primary"
              />
              {query ? (
                <button type="button" onClick={() => setQuery("")} aria-label="Clear architecture search" className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded text-text-subtle hover:bg-surface-2">
                  <X className="size-4" aria-hidden />
                </button>
              ) : null}
            </label>
          </div>

          <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Architecture views">
            {ARCHITECTURE_VIEWS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={view === item.id}
                onClick={() => selectView(item.id)}
                className={`min-h-11 rounded-md border px-3 text-xs font-bold transition-colors ${view === item.id ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2 hover:text-text-strong"}`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-[10.5px] text-text-subtle">{ARCHITECTURE_VIEWS.find((item) => item.id === view)?.description}</p>
        </div>

        {view === "scale" ? (
          <ScaleController profile={profile} profileId={profileId} onProfile={setProfileId} scaleStage={scaleStage} onStage={setScaleStage} playing={playing} onPlay={playFlow} onPause={() => setPlaying(false)} />
        ) : null}

        <div className="grid min-h-[760px] 2xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="h-[760px] min-w-0 border-b border-border bg-[#f7f9fb] 2xl:border-b-0 2xl:border-r">
            <ReactFlow
              key={view}
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodeClick={(_, node) => setSelectedId(node.id)}
              fitView
              fitViewOptions={{ padding: 0.2, maxZoom: 0.92 }}
              minZoom={0.25}
              maxZoom={1.6}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#cbd5e1" />
              <MiniMap
                pannable
                zoomable
                nodeColor={(node) => PLANE_META[(node.data as DiagramNodeData).component.plane].color}
                maskColor="rgba(244, 246, 248, 0.76)"
                className="!border !border-border !bg-white"
              />
              <Controls showInteractive={false} className="!border-border !shadow-card" />
            </ReactFlow>
          </div>
          <ComponentDetail component={selected} connections={viewConnections} onSelect={setSelectedId} />
        </div>

        <div className="border-t border-border bg-white px-5 py-4">
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {Object.entries(FLOW_META).map(([id, meta]) => (
              <span key={id} className="inline-flex items-center gap-2 text-[10px] font-semibold text-text-muted">
                <span className="h-0.5 w-7" style={{ background: meta.color }} /> {meta.label} flow
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface p-5 shadow-card" aria-labelledby="architecture-inventory-heading">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">Complete component inventory</p>
            <h2 id="architecture-inventory-heading" className="mt-1 text-lg font-bold text-text-strong">{inventoryMatches.length} of {COMPONENTS.length} boxes mapped</h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">Select any component to open the view that contains it and inspect its input, processing, output, scaling, security, recovery, and proof contract.</p>
          </div>
          <a href="https://aws.amazon.com/architecture/icons/" target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">
            Official AWS icon source <ExternalLink className="size-3.5" aria-hidden />
          </a>
        </div>
        <div className="mt-5 grid gap-5">
          {(Object.keys(PLANE_META) as ArchitecturePlane[]).map((planeId) => {
            const planeComponents = inventoryMatches.filter((component) => component.plane === planeId);
            if (planeComponents.length === 0) return null;
            const meta = PLANE_META[planeId];
            return (
              <div key={planeId}>
                <div className="flex items-center gap-2">
                  <span className="size-2.5 rounded-full" style={{ background: meta.color }} />
                  <h3 className="text-xs font-bold text-text-strong">{meta.label} plane</h3>
                  <span className="font-mono text-[10px] text-text-subtle">{planeComponents.length}</span>
                </div>
                <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {planeComponents.map((component) => (
                    <button
                      key={component.id}
                      type="button"
                      onClick={() => {
                        const nextView = preferredView(component);
                        selectView(nextView);
                        setSelectedId(component.id);
                        window.setTimeout(() => document.getElementById("architecture-diagram-top")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
                      }}
                      className="flex min-h-16 items-center gap-3 rounded-lg border border-border bg-white p-3 text-left transition-colors hover:border-gov-primary hover:bg-gov-primary-lighter"
                    >
                      <span className="grid size-9 shrink-0 place-items-center rounded-md bg-surface-2">
                        {component.icon ? <img src={component.icon} alt="" className="size-7 object-contain" /> : <UsersRound className="size-5 text-gov-primary" aria-hidden />}
                      </span>
                      <span className="min-w-0">
                        <span className="block text-[11px] font-bold text-text-strong">{component.label}</span>
                        <span className="mt-0.5 block truncate text-[9.5px] text-text-subtle">{component.service}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function ScaleController({
  profile,
  profileId,
  onProfile,
  scaleStage,
  onStage,
  playing,
  onPlay,
  onPause,
}: {
  profile: ScaleProfile;
  profileId: ScaleProfile["id"];
  onProfile: (id: ScaleProfile["id"]) => void;
  scaleStage: number;
  onStage: (stage: number) => void;
  playing: boolean;
  onPlay: () => void;
  onPause: () => void;
}) {
  const stage = SCALE_STAGES[scaleStage - 1];
  return (
    <div className="border-b border-border bg-gov-primary-lighter/60 px-4 py-4 sm:px-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <fieldset>
          <legend className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-subtle">Measured workload profile</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {SCALE_PROFILES.map((candidate) => (
              <label key={candidate.id} className={`cursor-pointer rounded-md border px-3 py-2 ${profileId === candidate.id ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted"}`}>
                <input
                  type="radio"
                  name="architecture-scale-profile"
                  value={candidate.id}
                  checked={profileId === candidate.id}
                  onChange={() => onProfile(candidate.id)}
                  aria-label={`${candidate.label} profile, ${candidate.partitions} partitions`}
                  className="sr-only"
                />
                <span className="font-mono text-xs font-bold">{candidate.label}</span>
                <span className={`ml-2 text-[9px] ${profileId === candidate.id ? "text-white/70" : "text-text-subtle"}`}>{candidate.partitions} parts</span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:min-w-[620px]">
          <ScaleMetric label="Records" value={number.format(profile.records)} />
          <ScaleMetric label="Measured wall time" value={`${profile.wallSeconds.toFixed(3)} sec`} />
          <ScaleMetric label="Peak throughput" value={`${number.format(profile.peakRps)} rec/s`} />
          <ScaleMetric label="Accrued estimate" value={money.format(profile.accruedCost)} />
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-3 xl:flex-row xl:items-center">
        <div className="flex shrink-0 gap-2">
          <button type="button" onClick={playing ? onPause : onPlay} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-action px-4 text-xs font-bold text-white hover:bg-action-hover">
            {playing ? <Pause className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}
            {playing ? "Pause flow" : scaleStage >= SCALE_STAGES.length ? "Replay flow" : "Play flow"}
          </button>
          <span className="inline-flex min-h-11 items-center rounded-md border border-border bg-white px-3 font-mono text-xs font-bold text-gov-primary">Step {scaleStage} / 9</span>
        </div>
        <div className="flex min-w-0 flex-1 gap-1 overflow-x-auto pb-1" aria-label="Scale flow stages">
          {SCALE_STAGES.map((candidate) => (
            <button
              key={candidate.id}
              type="button"
              onClick={() => { onPause(); onStage(candidate.id); }}
              aria-label={`Show scale stage ${candidate.id}: ${candidate.label}`}
              className={`grid min-h-11 min-w-11 place-items-center rounded-md border font-mono text-[10px] font-bold ${candidate.id === scaleStage ? "border-gold bg-gold-soft text-gold-ink" : candidate.id < scaleStage ? "border-success/35 bg-success-soft text-success" : "border-border bg-white text-text-subtle"}`}
            >
              {candidate.id < scaleStage ? <CheckCircle2 className="size-4" aria-hidden /> : candidate.id}
            </button>
          ))}
        </div>
      </div>
      {stage ? (
        <div className="mt-3 flex items-start gap-3 rounded-lg border border-gold/30 bg-white px-4 py-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-gold-soft font-mono text-xs font-bold text-gold-ink">{stage.id}</span>
          <div>
            <p className="text-xs font-bold text-text-strong">{stage.label}</p>
            <p className="mt-1 text-[10.5px] leading-4 text-text-muted">{stage.detail}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ComponentDetail({ component, connections, onSelect }: { component: ArchitectureComponent | null; connections: ReturnType<typeof connectionsForView>; onSelect: (id: string) => void }) {
  if (!component) return <aside className="p-5 text-sm text-text-muted">Select a box to inspect it.</aside>;
  const plane = PLANE_META[component.plane];
  const deployment = DEPLOYMENT_META[component.deployment];
  const related = connections.filter((connection) => connection.source === component.id || connection.target === component.id);
  return (
    <aside className="min-w-0 bg-white p-5" aria-live="polite">
      <div className="flex items-start gap-3">
        <span className="grid size-12 shrink-0 place-items-center rounded-lg border border-border" style={{ background: plane.tint }}>
          {component.icon ? <img src={component.icon} alt="" className="size-9 object-contain" /> : <UsersRound className="size-7 text-gov-primary" aria-hidden />}
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: plane.color }}>{plane.label} plane</p>
          <h3 className="mt-1 text-lg font-bold leading-tight text-text-strong">{component.label}</h3>
          <p className="mt-1 text-[10.5px] text-text-subtle">{component.service}</p>
          <span className={`mt-2 inline-flex rounded-full border px-2 py-1 text-[9px] font-bold uppercase tracking-wide ${deployment.className}`}>{deployment.label}</span>
        </div>
      </div>
      <p className="mt-4 text-xs leading-5 text-text-muted">{component.summary}</p>
      <dl className="mt-5 space-y-4">
        <Detail label="Receives" value={component.receives} />
        <Detail label="What happens" value={component.processing} />
        <Detail label="Emits" value={component.emits} />
        <Detail label="How it scales" value={component.scaling} icon={Gauge} />
        <Detail label="Failure and recovery" value={component.resilience} icon={Activity} />
        <Detail label="Security boundary" value={component.security} icon={ShieldCheck} />
        <Detail label="Proof retained" value={component.evidence} icon={CheckCircle2} />
      </dl>
      {related.length > 0 ? (
        <div className="mt-5 border-t border-border pt-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-subtle">Connected flows</p>
          <div className="mt-2 space-y-1.5">
            {related.map((connection) => {
              const otherId = connection.source === component.id ? connection.target : connection.source;
              const other = COMPONENTS.find((candidate) => candidate.id === otherId);
              return (
                <button key={connection.id} type="button" onClick={() => onSelect(otherId)} className="flex min-h-10 w-full items-center gap-2 rounded-md border border-border bg-surface px-3 text-left text-[10px] text-text-muted hover:bg-surface-2">
                  <span className="size-2 shrink-0 rounded-full" style={{ background: FLOW_META[connection.kind].color }} />
                  <span className="min-w-0 flex-1 truncate">{connection.label}</span>
                  <ArrowRight className="size-3 shrink-0" aria-hidden />
                  <span className="max-w-32 truncate font-semibold text-text-strong">{other?.label ?? otherId}</span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
      {component.docsUrl ? (
        <a href={component.docsUrl} target="_blank" rel="noreferrer" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">
          Open AWS documentation <ExternalLink className="size-3.5" aria-hidden />
        </a>
      ) : null}
    </aside>
  );
}

function Detail({ label, value, icon: Icon }: { label: string; value: string; icon?: typeof Gauge }) {
  return (
    <div className="border-l-2 border-border pl-3">
      <dt className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-[0.13em] text-text-subtle">
        {Icon ? <Icon className="size-3" aria-hidden /> : null} {label}
      </dt>
      <dd className="mt-1 text-[10.5px] leading-4 text-text-muted">{value}</dd>
    </div>
  );
}

function Fact({ icon: Icon, value, label, detail }: { icon: typeof Activity; value: string; label: string; detail: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-soft">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-xl font-bold text-text-strong">{value}</span>
        <span className="grid size-8 place-items-center rounded-md bg-gov-primary-lighter text-gov-primary"><Icon className="size-4" aria-hidden /></span>
      </div>
      <p className="mt-2 text-[10.5px] font-bold text-text-strong">{label}</p>
      <p className="mt-0.5 text-[9.5px] text-text-subtle">{detail}</p>
    </div>
  );
}

function FlowSummary({ color, label, text }: { color: string; label: string; text: string }) {
  return (
    <div className="border-white/10 px-5 py-4 md:border-r last:border-r-0">
      <p className="flex items-center gap-2 text-xs font-bold"><span className="size-2 rounded-full" style={{ background: color }} /> {label}</p>
      <p className="mt-1 text-[10px] leading-4 text-white/60">{text}</p>
    </div>
  );
}

function ScaleMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-white px-3 py-2" role="group" aria-label={`${label}: ${value}`}>
      <p className="text-[8.5px] font-bold uppercase tracking-wide text-text-subtle">{label}</p>
      <p className="mt-1 font-mono text-[11px] font-bold text-text-strong">{value}</p>
    </div>
  );
}

function badgeFor(id: string, profile: ScaleProfile): string | null {
  if (id === "scale-control") return number.format(profile.records);
  if (id === "scale-workflow" || id === "worker-queue") return `${profile.partitions} parts`;
  if (id === "scale-ledger") return `${profile.partitions} receipts`;
  if (id === "scale-worker") return "4 concurrent";
  if (id === "scale-lake") return `${number.format(profile.curated)} curated`;
  if (id === "athena") return "10 GiB cap";
  if (id === "scale-export") return `${number.format(profile.curated)} rows`;
  return null;
}

function preferredView(component: ArchitectureComponent): ArchitectureView {
  if (component.positions.scale) return "scale";
  if (component.positions.mission) return "mission";
  if (component.positions.security) return "security";
  if (component.positions.operations) return "operations";
  return "platform";
}

export default ArchitectureExplorer;
