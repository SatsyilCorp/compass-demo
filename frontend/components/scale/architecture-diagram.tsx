"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowDown,
  BarChart3,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  CloudCog,
  Database,
  Download,
  Fingerprint,
  Gauge,
  HardDrive,
  Layers3,
  ListOrdered,
  LockKeyhole,
  Network,
  Scale,
  ShieldCheck,
  UserRoundCog,
  type LucideIcon,
} from "lucide-react";

type PlaneId = "control" | "data" | "intelligence" | "evidence";

type ArchitectureNode = {
  id: string;
  order: number;
  plane: PlaneId;
  label: string;
  role: string;
  proof: string;
  icon: LucideIcon;
};

const PLANES: { id: PlaneId; label: string; description: string; tone: string }[] = [
  { id: "control", label: "Control plane", description: "Operator intent, identity, policy, orchestration, and limits", tone: "border-info/35 bg-info-soft" },
  { id: "data", label: "Data plane", description: "Backpressure, bounded generation, quality, and lake zones", tone: "border-gov-primary/30 bg-gov-primary-lighter" },
  { id: "intelligence", label: "Intelligence plane", description: "Catalog, columnar conversion, and full-corpus analysis", tone: "border-gold/45 bg-gold-soft" },
  { id: "evidence", label: "Evidence plane", description: "Metrics, cost, recovery, and audit proof", tone: "border-success/35 bg-success-soft" },
];

const NODES: ArchitectureNode[] = [
  { id: "operator", order: 1, plane: "control", label: "Scale Lab", role: "A power user selects a fixed workload and previews its exact plan.", proof: "Profile, seed, partition ceiling, and cost ceiling are bound before launch.", icon: UserRoundCog },
  { id: "identity", order: 2, plane: "control", label: "Identity and role gate", role: "Authentication and the power-user policy protect every scale command.", proof: "The request carries a verified identity and an auditable role decision.", icon: LockKeyhole },
  { id: "scale-api", order: 3, plane: "control", label: "Scale Plan and Run Gate", role: "A narrow interface validates fixed profiles, plan expiry, idempotency, price freshness, and cost bounds.", proof: "Unbounded record counts and stale cost evidence never cross the interface.", icon: Scale },
  { id: "orchestrator", order: 4, plane: "control", label: "Standard workflow", role: "A durable workflow dispatches partitions, waits for completion, converts outputs, and finalizes evidence.", proof: "Cancellation, retry, timeout, and failure compensation remain explicit.", icon: CloudCog },
  { id: "buffer", order: 5, plane: "data", label: "Backpressure buffer", role: "A queue absorbs partition bursts and isolates dispatch from processing capacity.", proof: "Concurrency is bounded, retries are visible, and poison messages move to a recovery queue.", icon: Network },
  { id: "generator", order: 6, plane: "data", label: "Partition workers", role: "Deterministic workers create grants, finance, milestones, documents, licenses, and stream events.", proof: "The same profile, seed, and partition coordinates reproduce identical records.", icon: Boxes },
  { id: "raw-lake", order: 7, plane: "data", label: "Immutable landing zone", role: "Each worker streams a bounded compressed JSON Lines source object.", proof: "Landing bytes have SHA-256 evidence and remain replayable for the retention window.", icon: HardDrive },
  { id: "quality", order: 8, plane: "data", label: "Quality and quarantine", role: "Schema, required-field, relationship, range, and synthetic-label rules run record by record.", proof: "Every rejected record is counted and quarantined with rule-level reasons.", icon: ShieldCheck },
  { id: "curated", order: 9, plane: "data", label: "Curated JSON Lines", role: "Passing records publish into run-partitioned governed objects beside a Partition Receipt.", proof: "A transactional ledger commit prevents retry duplication in terminal counts.", icon: Database },
  { id: "catalog", order: 10, plane: "intelligence", label: "Catalog and scan guard", role: "Projected Glue tables expose only the selected run to an Athena workgroup with a hard scan cutoff.", proof: "Every query is partition-pruned and cannot exceed the deployed byte ceiling.", icon: Layers3 },
  { id: "parquet", order: 11, plane: "intelligence", label: "Parquet conversion", role: "Athena converts all six curated datasets into compressed columnar run partitions.", proof: "Query state, scanned bytes, output bytes, and object checksums remain attached to the run.", icon: Database },
  { id: "intelligence", order: 12, plane: "intelligence", label: "Full-corpus intelligence", role: "Finalization merges aggregate partials from every Partition Receipt into topics and anomaly counts.", proof: "Coverage is the full synthetic corpus and semantic embedding coverage is explicitly zero.", icon: BrainCircuit },
  { id: "serving", order: 13, plane: "intelligence", label: "Scale evidence projection", role: "The Scale Lab reads one compact run snapshot instead of scanning the lake during interaction.", proof: "The interface stays responsive while preserving exact corpus and partition totals.", icon: BarChart3 },
  { id: "run-ledger", order: 14, plane: "evidence", label: "Run state ledger", role: "Plans, idempotency keys, stage state, counters, leases, cancellation, and receipts remain durable.", proof: "A repeated command resolves to the original operation instead of duplicating work.", icon: Fingerprint },
  { id: "telemetry", order: 15, plane: "evidence", label: "Operations and cost", role: "Metrics, traces, queue depth, throughput, and priced service quantities form one evidence view.", proof: "Operators see recovery depth and estimated spend against the enforced ceiling.", icon: Activity },
  { id: "export", order: 16, plane: "evidence", label: "Governed release", role: "An asynchronous worker seals the exact Parquet objects into an immutable checksummed release manifest.", proof: "The receipt identifies row count, bytes, logical object, expiry, and checksum.", icon: Download },
  { id: "audit", order: 17, plane: "evidence", label: "Terminal manifest", role: "The final manifest seals the workload, quality, intelligence, outputs, controls, and correlation chain.", proof: "A presenter can prove what happened without exposing physical infrastructure identifiers.", icon: CheckCircle2 },
];

export function ArchitectureDiagram() {
  const [activePlane, setActivePlane] = useState<PlaneId | "all">("all");
  const [activeNodeId, setActiveNodeId] = useState("scale-api");
  const activeNode = useMemo(() => NODES.find((node) => node.id === activeNodeId) ?? NODES[0], [activeNodeId]);

  return (
    <section className="mt-6 rounded-xl border border-border bg-surface p-5 shadow-card" aria-labelledby="scale-architecture-heading">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">Production reference architecture</p>
          <h2 id="scale-architecture-heading" className="mt-1 flex items-center gap-2 text-lg font-bold text-text-strong">
            <Layers3 className="size-5 text-gov-primary" aria-hidden /> Four-plane workload path
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">
            Select a plane or step to explain how bounded control becomes scalable data work and verifiable evidence.
          </p>
        </div>
        <div className="flex flex-wrap gap-2" aria-label="Architecture plane filter">
          <PlaneButton active={activePlane === "all"} onClick={() => setActivePlane("all")}>
            All planes
          </PlaneButton>
          {PLANES.map((plane) => (
            <PlaneButton key={plane.id} active={activePlane === plane.id} onClick={() => setActivePlane(plane.id)}>
              {plane.label.replace(" plane", "")}
            </PlaneButton>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-3 xl:grid-cols-4">
        {PLANES.map((plane) => {
          const muted = activePlane !== "all" && activePlane !== plane.id;
          const nodes = NODES.filter((node) => node.plane === plane.id);
          return (
            <section
              key={plane.id}
              aria-labelledby={`architecture-plane-${plane.id}`}
              className={`rounded-xl border p-3 transition-opacity ${plane.tone} ${muted ? "opacity-35" : "opacity-100"}`}
            >
              <header className="mb-3 border-b border-black/10 pb-2">
                <h3 id={`architecture-plane-${plane.id}`} className="text-xs font-bold text-text-strong">{plane.label}</h3>
                <p className="mt-1 text-[10px] leading-4 text-text-muted">{plane.description}</p>
              </header>
              <div className="space-y-2">
                {nodes.map((node) => {
                  const Icon = node.icon;
                  const active = node.id === activeNodeId;
                  return (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() => {
                        setActiveNodeId(node.id);
                        setActivePlane(node.plane);
                      }}
                      aria-pressed={active}
                      className={`flex min-h-14 w-full items-center gap-2.5 rounded-lg border px-2.5 py-2 text-left transition-all ${
                        active ? "border-gov-primary bg-white shadow-card" : "border-white/75 bg-white/65 hover:bg-white"
                      }`}
                    >
                      <span className={`grid size-7 shrink-0 place-items-center rounded-md ${active ? "bg-gov-primary text-white" : "bg-white text-gov-primary"}`}>
                        <Icon className="size-3.5" aria-hidden />
                      </span>
                      <span className="min-w-0">
                        <span className="block font-mono text-[9px] font-bold text-text-subtle">STEP {String(node.order).padStart(2, "0")}</span>
                        <span className="block text-[11px] font-semibold leading-4 text-text-strong">{node.label}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>

      <div className="mt-4 grid gap-4 rounded-xl border border-gov-primary/20 bg-gov-primary-lighter p-4 lg:grid-cols-[auto_minmax(0,1fr)_minmax(260px,0.55fr)] lg:items-start">
        <span className="grid size-11 place-items-center rounded-lg bg-gov-primary text-white">
          <activeNode.icon className="size-5" aria-hidden />
        </span>
        <div>
          <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-gov-primary-vivid">Step {activeNode.order} · {PLANES.find((plane) => plane.id === activeNode.plane)?.label}</p>
          <h3 className="mt-1 text-sm font-bold text-text-strong">{activeNode.label}</h3>
          <p className="mt-1 text-xs leading-5 text-text-muted">{activeNode.role}</p>
        </div>
        <div className="rounded-lg border border-white bg-white/75 p-3">
          <p className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wide text-success">
            <Gauge className="size-3" aria-hidden /> Proof produced
          </p>
          <p className="mt-1.5 text-[10.5px] leading-4 text-text-muted">{activeNode.proof}</p>
        </div>
      </div>

      <details className="mt-4 rounded-lg border border-border bg-surface-2">
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-4 text-xs font-semibold text-text-strong">
          <ListOrdered className="size-4 text-gov-primary" aria-hidden /> Accessible ordered flow
        </summary>
        <ol className="grid gap-2 border-t border-border px-4 py-3 sm:grid-cols-2 lg:grid-cols-3">
          {NODES.map((node) => (
            <li key={node.id} className="flex items-start gap-2 text-[10.5px] leading-4 text-text-muted">
              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-gov-primary font-mono text-[9px] font-bold text-white">{node.order}</span>
              <span><strong className="text-text-strong">{node.label}:</strong> {node.role}</span>
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}

function PlaneButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-h-10 rounded-full border px-3 text-[10px] font-bold uppercase tracking-wide transition-colors ${
        active ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2"
      }`}
    >
      {children}
    </button>
  );
}
