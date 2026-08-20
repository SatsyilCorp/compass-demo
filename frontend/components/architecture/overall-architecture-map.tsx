"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowDown,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Database,
  ExternalLink,
  FileCheck2,
  GitBranch,
  Maximize2,
  Minimize2,
  Network,
  ShieldCheck,
  UsersRound,
  X,
} from "lucide-react";

import {
  COMPONENTS,
  CONNECTIONS,
  FLOW_META,
  PLANE_META,
  type ArchitectureComponent,
} from "./model";
import {
  OVERALL_FLOW_STEPS,
  overallGroup,
  type OverallArchitectureGroupId,
} from "./overall-model";

const DEPLOYMENT_META: Record<ArchitectureComponent["deployment"], { label: string; className: string; dot: string }> = {
  core: { label: "IaC-declared core", className: "border-success/30 bg-success-soft text-success", dot: "bg-success" },
  scale: { label: "IaC-declared scale", className: "border-info/30 bg-info-soft text-info", dot: "bg-info" },
  conditional: { label: "Conditional integration", className: "border-gold/40 bg-gold-soft text-gold-ink", dot: "bg-gold" },
  logical: { label: "Logical boundary", className: "border-border bg-surface-2 text-text-muted", dot: "bg-text-subtle" },
};

const PRODUCT_SURFACES = [
  { label: "Live source operations", href: "/admin/acquisition/" },
  { label: "Ingest and quality", href: "/ingest/" },
  { label: "Governed catalog", href: "/catalog/" },
  { label: "Topic intelligence", href: "/intelligence/" },
  { label: "Decision brief", href: "/dashboard/" },
  { label: "Portable preview and governed release", href: "/export/" },
  { label: "License posture", href: "/licenses/" },
  { label: "MLOps", href: "/admin/mlops/" },
  { label: "Scale Lab", href: "/admin/scale/" },
  { label: "Requirements proof", href: "/admin/requirements/" },
] as const;

const SOURCE_FAMILIES = [
  { label: "Mission users", detail: "Power user, viewer, reviewer, operator" },
  { label: "USAspending", detail: "Five-minute backend public award poll" },
  { label: "Grants.gov", detail: "Fifteen-minute backend DOD and ONR opportunity poll" },
  { label: "Crossref", detail: "Hourly backend exact ONR funder publication poll" },
  { label: "Federal Register", detail: "Thirty-minute backend Navy and ONR notice poll" },
  { label: "SBIR snapshot", detail: "Monthly public file with API health shown separately" },
  { label: "Authorized rehearsal files", detail: "Explicit mode only: CSV, JSON, PDF, DOCX, TXT, and other bounded formats" },
  { label: "Synthetic rehearsal pulse", detail: "Explicit mode only: deterministic one-second or two-second operator pulse" },
] as const;

const TARGET_GROUPS = [
  {
    icon: ShieldCheck,
    title: "Government access boundary",
    detail: "DoD ICAM and CAC/PIV, CAP or BCAP, VDSS, approved private ingress, and inspected TLS.",
  },
  {
    icon: Network,
    title: "IL4/IL5 enclave hardening",
    detail: "Private or FIPS endpoints, Network Firewall, VPC Flow Logs, central DNS, controlled egress, and multi-account segmentation.",
  },
  {
    icon: FileCheck2,
    title: "Government operations and accreditation",
    detail: "VDMS, TCCM, CSSP or SIEM export, eMASS evidence, inherited controls, and the Government ATO process.",
  },
  {
    icon: Database,
    title: "Optional data-platform seam",
    detail: "Databricks or Advana can connect through standard APIs, SQL, Parquet, Delta, and S3 without moving platform logic into the Compass frontend.",
  },
] as const;

export function OverallArchitectureMap() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [presentationMode, setPresentationMode] = useState(false);
  const selected = useMemo(
    () => COMPONENTS.find((component) => component.id === selectedId) ?? null,
    [selectedId],
  );

  useEffect(() => {
    if (!selected && !presentationMode) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (selected) setSelectedId(null);
      else setPresentationMode(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [presentationMode, selected]);

  useEffect(() => {
    if (!presentationMode) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [presentationMode]);

  return (
    <>
      <section
        className={presentationMode
          ? "fixed inset-0 z-50 overflow-y-auto bg-[#edf2f6] p-3 sm:p-5"
          : "overflow-hidden rounded-xl border border-[#9aa9b8] bg-[#edf2f6] shadow-card"}
        aria-labelledby="overall-architecture-title"
      >
        <div className={presentationMode ? "mx-auto max-w-[1760px] overflow-hidden rounded-xl border border-[#9aa9b8] bg-[#edf2f6] shadow-card" : ""}>
          <header className="sticky top-0 z-20 border-b border-white/10 bg-[#122f4a] px-5 py-5 text-white sm:px-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.17em] text-[#ffca73]">Complete system overview</p>
                <h2 id="overall-architecture-title" className="mt-2 text-xl font-bold sm:text-2xl">Compass AWS reference architecture</h2>
                <p className="mt-2 max-w-4xl text-xs leading-5 text-white/72 sm:text-sm sm:leading-6">
                  One picture follows live public authorities through source-safe backend polling, raw retention, governance, exact evidence identity, real model receipts, decision products, DevSecOps, security, operations, and the separate IL4/IL5 target boundary. Synthetic rehearsal is isolated and requires an explicit user choice. Select any AWS component for its full contract.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-success/40 bg-success/15 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wide text-[#b6f0cd]">Source-controlled AWS design</span>
                <button
                  type="button"
                  onClick={() => setPresentationMode((current) => !current)}
                  className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/20 bg-white/10 px-3 text-[10px] font-bold uppercase tracking-wide text-white hover:bg-white/15"
                >
                  {presentationMode ? <Minimize2 className="size-4" aria-hidden /> : <Maximize2 className="size-4" aria-hidden />}
                  {presentationMode ? "Exit presentation view" : "Open presentation view"}
                </button>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2" aria-label="Deployment status legend">
              {Object.values(DEPLOYMENT_META).map((status) => (
                <span key={status.label} className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[8.5px] font-bold uppercase tracking-wide text-white/78">
                  <span className={`size-1.5 rounded-full ${status.dot}`} /> {status.label}
                </span>
              ))}
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[#ffca73]/30 bg-[#ffca73]/10 px-2.5 py-1 text-[8.5px] font-bold uppercase tracking-wide text-[#ffda9c]">
                <span className="size-1.5 rounded-full bg-[#ffb84d]" /> Target or external
              </span>
            </div>
          </header>

          <FlowRibbon />

          <div className="overflow-x-auto" role="region" aria-label="Complete AWS architecture diagram" tabIndex={0}>
            <div className="min-w-[1380px] space-y-3 p-4 sm:p-5">
              <div className="grid grid-cols-[220px_minmax(0,1fr)] gap-3">
                <ExternalSources onSelect={() => setSelectedId("personas")} />

                <section className="rounded-xl border-[3px] border-[#527ea3] bg-white/55 p-3" aria-labelledby="aws-cloud-boundary-heading">
                  <BoundaryHeader
                    icon="/aws-icons/cloudformation.svg"
                    eyebrow="AWS cloud and Satsyil account boundary"
                    title="Commercial AWS proving environment | us-east-1"
                    badge="Declared in IaC"
                    id="aws-cloud-boundary-heading"
                  />

                  <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(330px,0.65fr)]">
                    <ArchitectureGroup
                      groupId="edge"
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                      columns="grid-cols-5"
                      tone="edge"
                    />
                    <MissionSurfaces />
                  </div>

                  <VerticalFlow label="HTTPS, OIDC, JWT, API invocation, and signed object references" />

                  <section className="rounded-xl border-2 border-[#7d95aa] bg-[#f8fafc] p-3" aria-labelledby="aws-region-boundary-heading">
                    <BoundaryHeader
                      icon="/aws-icons/vpc.svg"
                      eyebrow="AWS Region boundary"
                      title="Managed service plane and customer VPC"
                      badge="us-east-1"
                      id="aws-region-boundary-heading"
                      compact
                    />

                    <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(420px,0.75fr)]">
                      <VpcBoundary selectedId={selectedId} onSelect={setSelectedId} />

                      <div className="space-y-3">
                        <ArchitectureGroup groupId="regional-compute" selectedId={selectedId} onSelect={setSelectedId} columns="grid-cols-2" tone="managed" />
                        <ArchitectureGroup groupId="ingestion" selectedId={selectedId} onSelect={setSelectedId} columns="grid-cols-2" tone="managed" />
                        <ArchitectureGroup groupId="scale" selectedId={selectedId} onSelect={setSelectedId} columns="grid-cols-2" tone="managed" />
                        <ArchitectureGroup groupId="ml" selectedId={selectedId} onSelect={setSelectedId} columns="grid-cols-2" tone="managed" />
                      </div>
                    </div>

                    <VerticalFlow label="Encryption, least privilege, metrics, traces, findings, notifications, and immutable receipts" />

                    <div className="grid gap-3 xl:grid-cols-2">
                      <ArchitectureGroup groupId="security" selectedId={selectedId} onSelect={setSelectedId} columns="grid-cols-3" tone="security" />
                      <ArchitectureGroup groupId="operations" selectedId={selectedId} onSelect={setSelectedId} columns="grid-cols-2" tone="operations" />
                    </div>
                  </section>

                  <div className="mt-3">
                    <DeliveryBoundary selectedId={selectedId} onSelect={setSelectedId} />
                  </div>
                </section>
              </div>

              <TargetBoundary />

              <div className="grid gap-2 lg:grid-cols-3" aria-label="Architecture truth notes">
                <TruthNote title="Source cadence contract" detail="The source-controlled controller keeps running until an operator stops it. EventBridge invokes USAspending, Grants.gov, Crossref, and Federal Register at independent source-safe cadences. The browser reads retained receipts and change events without calling a public authority. SBIR uses its public monthly snapshot while its API is degraded. Synthetic pulse data is isolated behind explicit rehearsal mode. Current execution must be verified from an operational receipt." />
                <TruthNote title="IaC placement" detail="The application IaC places thirteen database-facing Lambda adapters and Aurora across two private subnets. Eight other Lambda adapters remain in the regional managed service plane. One NAT gateway is the declared demonstration-cost tradeoff. S3 and DynamoDB gateway endpoints keep those private-subnet service routes off the internet path. Stack outputs and runtime evidence confirm the environment actually deployed." />
                <TruthNote title="Authorization boundary" detail="The IL4/IL5 lane is a proposed target. This source-controlled commercial AWS design is not an ATO, FedRAMP High authorization, or completed Government integration." />
              </div>
            </div>
          </div>
        </div>
      </section>

      {selected ? (
        <ArchitectureDetailDrawer
          component={selected}
          onClose={() => setSelectedId(null)}
          onSelect={setSelectedId}
        />
      ) : null}
    </>
  );
}

function FlowRibbon() {
  return (
    <div className="border-b border-[#b7c3ce] bg-white px-4 py-3 sm:px-5">
      <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.15em] text-[#6a4a0e]">Numbered end-to-end mission flow</p>
      <div className="grid min-w-[980px] grid-cols-8 overflow-x-auto rounded-lg border border-[#b7c3ce] bg-[#f8fafc]" aria-label="Eight-step architecture flow">
        {OVERALL_FLOW_STEPS.map((step, index) => (
          <div key={step.number} className="relative min-h-[64px] border-r border-[#ccd5de] px-3 py-2.5 last:border-r-0">
            <div className="flex items-center gap-2">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-[#173d5c] font-mono text-[9px] font-bold text-white">{step.number}</span>
              <p className="text-[10px] font-bold text-[#162536]">{step.label}</p>
            </div>
            <p className="mt-1 text-[8.5px] leading-3 text-[#5d6b79]">{step.detail}</p>
            {index < OVERALL_FLOW_STEPS.length - 1 ? <ArrowRight className="absolute -right-2 top-1/2 z-10 size-4 -translate-y-1/2 rounded-full bg-white text-[#173d5c]" aria-hidden /> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function ExternalSources({ onSelect }: { onSelect: () => void }) {
  return (
    <aside className="self-start rounded-xl border-2 border-[#7d95aa] bg-white p-3" aria-labelledby="external-source-heading">
      <div className="flex items-center gap-2">
        <span className="grid size-9 place-items-center rounded-md bg-[#e9f1f7] text-[#173d5c]"><UsersRound className="size-5" aria-hidden /></span>
        <div>
          <p className="text-[8px] font-bold uppercase tracking-[0.13em] text-[#52626f]">External boundary</p>
          <h3 id="external-source-heading" className="text-[11px] font-bold text-[#162536]">People and source systems</h3>
        </div>
      </div>
      <div className="mt-3 space-y-2">
        {SOURCE_FAMILIES.map((source, index) => (
          <button
            key={source.label}
            type="button"
            onClick={index === 0 ? onSelect : undefined}
            className={`w-full rounded-lg border border-[#c8d2dc] bg-[#f8fafc] p-2.5 text-left ${index === 0 ? "hover:border-[#173d5c] hover:bg-[#edf4f9]" : "cursor-default"}`}
          >
            <span className="flex items-center gap-2">
              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-[#173d5c] font-mono text-[8px] font-bold text-white">{index + 1}</span>
              <span className="text-[9.5px] font-bold text-[#162536]">{source.label}</span>
            </span>
            <span className="mt-1 block text-[8.5px] leading-3.5 text-[#5d6b79]">{source.detail}</span>
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-center gap-2 text-[8px] font-bold uppercase tracking-wide text-[#173d5c]">
        HTTPS and governed upload <ArrowRight className="size-3.5" aria-hidden />
      </div>
    </aside>
  );
}

function VpcBoundary({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <section className="rounded-xl border-[3px] border-[#2774a6] bg-[#eef7fc] p-3" aria-labelledby="overall-vpc-heading">
      <BoundaryHeader
        icon="/aws-icons/vpc.svg"
        eyebrow="Customer VPC | IaC declared"
        title="10.42.0.0/16 | Two availability zones"
        badge="Private workloads"
        id="overall-vpc-heading"
        compact
      />

      <div className="mt-3">
        <ArchitectureGroup groupId="network" selectedId={selectedId} onSelect={onSelect} columns="grid-cols-4" tone="network" compact />
      </div>

      <div className="mt-3">
        <ArchitectureGroup groupId="endpoints" selectedId={selectedId} onSelect={onSelect} columns="grid-cols-2" tone="network" compact />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2" aria-label="Availability zone and subnet placement">
        <AvailabilityZone
          label="Availability Zone A"
          publicSubnet="Public A 10.42.0.0/24 | NAT and route"
          privateSubnet="Private A 10.42.10.0/24 | Lambda ENIs and Aurora writer"
        />
        <AvailabilityZone
          label="Availability Zone B"
          publicSubnet="Public B 10.42.1.0/24 | Route association"
          privateSubnet="Private B 10.42.11.0/24 | Lambda ENIs and Aurora reader"
        />
      </div>

      <div className="mt-3">
        <ArchitectureGroup groupId="application" selectedId={selectedId} onSelect={onSelect} columns="grid-cols-4" tone="application" compact />
      </div>

      <div className="mt-3">
        <ArchitectureGroup groupId="relational" selectedId={selectedId} onSelect={onSelect} columns="grid-cols-2" tone="data" compact />
      </div>
    </section>
  );
}

function AvailabilityZone({ label, publicSubnet, privateSubnet }: { label: string; publicSubnet: string; privateSubnet: string }) {
  return (
    <section className="rounded-lg border-2 border-dashed border-[#91a8bb] bg-white/80 p-2.5">
      <p className="text-[8px] font-bold uppercase tracking-[0.12em] text-[#536a7e]">{label}</p>
      <div className="mt-2 rounded-md border border-[#9bc6df] bg-[#edf8fd] px-2 py-1.5 text-[8.5px] font-semibold text-[#274d67]">{publicSubnet}</div>
      <div className="mt-1.5 rounded-md border border-[#8facc1] bg-[#edf3f7] px-2 py-1.5 text-[8.5px] font-semibold text-[#274052]">{privateSubnet}</div>
    </section>
  );
}

function ArchitectureGroup({
  groupId,
  selectedId,
  onSelect,
  columns,
  tone,
  compact = false,
}: {
  groupId: OverallArchitectureGroupId;
  selectedId: string | null;
  onSelect: (id: string) => void;
  columns: string;
  tone: "edge" | "network" | "application" | "data" | "managed" | "security" | "operations" | "delivery";
  compact?: boolean;
}) {
  const group = overallGroup(groupId);
  const tones = {
    edge: "border-[#8caec7] bg-[#f1f7fb]",
    network: "border-[#7ab0d1] bg-[#f4fafd]",
    application: "border-[#8aa3b8] bg-white",
    data: "border-[#74aa8e] bg-[#f0f8f3]",
    managed: "border-[#b7c3ce] bg-white",
    security: "border-[#c2a46c] bg-[#fffaf0]",
    operations: "border-[#9aabc0] bg-[#f6f8fb]",
    delivery: "border-[#9aabc0] bg-white",
  } as const;
  return (
    <section className={`rounded-lg border-2 p-2.5 ${tones[tone]}`} aria-label={`${group.label}: ${group.boundary}`}>
      <div className="flex items-start justify-between gap-2 border-b border-[#cbd5df] pb-2">
        <div>
          <div className="flex items-center gap-2">
            {group.step ? <span className="grid size-5 shrink-0 place-items-center rounded-full bg-[#173d5c] font-mono text-[8px] font-bold text-white">{group.step}</span> : null}
            <h3 className="text-[10px] font-bold text-[#162536]">{group.label}</h3>
          </div>
          <p className="mt-1 text-[8px] leading-3 text-[#52626f]">{group.boundary}</p>
        </div>
        <span className="shrink-0 rounded-full border border-[#bdc8d2] bg-white px-2 py-0.5 font-mono text-[7.5px] font-bold text-[#536575]">{group.componentIds.length}</span>
      </div>
      <div className={`mt-2 grid gap-1.5 ${columns}`}>
        {group.componentIds.map((id) => {
          const component = COMPONENTS.find((candidate) => candidate.id === id);
          if (!component) return null;
          return (
            <ServiceTile
              key={id}
              component={component}
              selected={selectedId === id}
              onSelect={onSelect}
              compact={compact}
            />
          );
        })}
      </div>
    </section>
  );
}

function ServiceTile({ component, selected, onSelect, compact }: { component: ArchitectureComponent; selected: boolean; onSelect: (id: string) => void; compact: boolean }) {
  const status = DEPLOYMENT_META[component.deployment];
  const plane = PLANE_META[component.plane];
  return (
    <button
      type="button"
      onClick={() => onSelect(component.id)}
      aria-label={`Inspect ${component.label}, ${component.service}`}
      className={`group flex min-w-0 items-center gap-2 rounded-md border bg-white text-left transition-all hover:-translate-y-px hover:border-[#173d5c] hover:shadow-soft ${compact ? "min-h-[46px] p-1.5" : "min-h-[54px] p-2"} ${selected ? "border-[#173d5c] ring-2 ring-[#ffca73]/65" : "border-[#cbd5df]"}`}
    >
      <span className={`grid shrink-0 place-items-center rounded border border-[#d4dce4] bg-[#f8fafc] ${compact ? "size-7" : "size-8"}`}>
        {component.icon ? <img src={component.icon} alt="" className={compact ? "size-5" : "size-6"} /> : <UsersRound className="size-4 text-[#173d5c]" aria-hidden />}
      </span>
      <span className="min-w-0 flex-1">
        <span className={`block font-bold leading-3 text-[#162536] ${compact ? "text-[7.8px]" : "text-[8.5px]"}`}>{component.label}</span>
        <span className="mt-0.5 flex items-center gap-1 text-[6.8px] font-bold uppercase tracking-wide" style={{ color: plane.color }}>
          <span className={`size-1.5 rounded-full ${status.dot}`} /> {status.label}
        </span>
      </span>
    </button>
  );
}

function MissionSurfaces() {
  return (
    <section className="rounded-lg border-2 border-[#9aaec0] bg-white p-2.5" aria-labelledby="mission-surface-heading">
      <div className="flex items-center gap-2 border-b border-[#cbd5df] pb-2">
        <span className="grid size-5 place-items-center rounded-full bg-[#173d5c] font-mono text-[8px] font-bold text-white">7</span>
        <div>
          <h3 id="mission-surface-heading" className="text-[10px] font-bold text-[#162536]">Compass mission product surfaces</h3>
          <p className="mt-0.5 text-[8px] text-[#52626f]">Governed consumer and operator experience</p>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        {PRODUCT_SURFACES.map((surface) => (
          <Link key={surface.href} href={surface.href} className="flex min-h-[32px] items-center justify-between gap-1 rounded-md border border-[#cbd5df] bg-[#f8fafc] px-2 text-[7.8px] font-bold leading-3 text-[#284a64] hover:border-[#173d5c] hover:bg-[#edf4f9]">
            {surface.label}<ArrowRight className="size-2.5 shrink-0" aria-hidden />
          </Link>
        ))}
      </div>
    </section>
  );
}

function DeliveryBoundary({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <section className="rounded-lg border-2 border-[#8fa1b1] bg-[#f3f6f8] p-2.5" aria-labelledby="delivery-boundary-heading">
      <div className="grid gap-3 xl:grid-cols-[minmax(0,0.62fr)_minmax(0,1.38fr)]">
        <ArchitectureGroup groupId="delivery" selectedId={selectedId} onSelect={onSelect} columns="grid-cols-3" tone="delivery" compact />
        <div className="rounded-lg border border-[#c4ced7] bg-white p-3">
          <div className="flex items-center gap-2">
            <GitBranch className="size-4 text-[#173d5c]" aria-hidden />
            <h3 id="delivery-boundary-heading" className="text-[10px] font-bold text-[#162536]">Immutable release path</h3>
          </div>
          <div className="mt-2 flex items-stretch">
            {["Protected branch", "Secrets, SAST, dependencies, IaC", "Tests, SBOM, signed evidence", "SAM and CloudFormation change set", "Deploy, smoke test, invalidate, rollback"].map((label, index, labels) => (
              <div key={label} className="contents">
                <div className="flex min-w-0 flex-1 items-center justify-center rounded-md border border-[#cbd5df] bg-[#f8fafc] px-2 py-2 text-center text-[7.5px] font-semibold leading-3 text-[#4d5f70]">{label}</div>
                {index < labels.length - 1 ? <ArrowRight className="mx-1 size-3.5 shrink-0 self-center text-[#173d5c]" aria-hidden /> : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function TargetBoundary() {
  return (
    <section className="rounded-xl border-[3px] border-dashed border-[#b28331] bg-[#fff9ed] p-3" aria-labelledby="target-boundary-heading">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[8px] font-bold uppercase tracking-[0.14em] text-[#7a5314]">Separate target and external dependency boundary</p>
          <h3 id="target-boundary-heading" className="mt-1 text-[12px] font-bold text-[#3d301d]">Government IL4/IL5 landing zone and optional enterprise integrations</h3>
        </div>
        <span className="rounded-full border border-[#c79a49] bg-white px-2.5 py-1 text-[8px] font-bold uppercase tracking-wide text-[#7a5314]">Not deployed here</span>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2">
        {TARGET_GROUPS.map(({ icon: Icon, title, detail }) => (
          <article key={title} className="rounded-lg border border-[#d9bb82] bg-white p-3">
            <div className="flex items-center gap-2">
              <span className="grid size-8 shrink-0 place-items-center rounded-md bg-[#fff1d4] text-[#7a5314]"><Icon className="size-4" aria-hidden /></span>
              <h4 className="text-[9px] font-bold leading-3 text-[#3d301d]">{title}</h4>
            </div>
            <p className="mt-2 text-[8px] leading-3.5 text-[#725d3d]">{detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function BoundaryHeader({ icon, eyebrow, title, badge, id, compact = false }: { icon: string; eyebrow: string; title: string; badge: string; id: string; compact?: boolean }) {
  return (
    <header className={`flex items-center justify-between gap-3 rounded-lg bg-[#173d5c] text-white ${compact ? "px-3 py-2.5" : "px-4 py-3"}`}>
      <div className="flex items-center gap-2.5">
        <span className={`grid shrink-0 place-items-center rounded-md border border-white/20 bg-white ${compact ? "size-8" : "size-10"}`}><img src={icon} alt="" className={compact ? "size-6" : "size-7"} /></span>
        <div>
          <p className="text-[7.5px] font-bold uppercase tracking-[0.13em] text-[#ffca73]">{eyebrow}</p>
          <h3 id={id} className={`mt-0.5 font-bold ${compact ? "text-[11px]" : "text-[13px]"}`}>{title}</h3>
        </div>
      </div>
      <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[7.5px] font-bold uppercase tracking-wide text-white/85">{badge}</span>
    </header>
  );
}

function VerticalFlow({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-2 text-[7.5px] font-bold uppercase tracking-wide text-[#355873]" aria-label={label}>
      <span className="h-px flex-1 bg-[#aebbc7]" />
      <ArrowDown className="size-3.5" aria-hidden /> {label} <ArrowDown className="size-3.5" aria-hidden />
      <span className="h-px flex-1 bg-[#aebbc7]" />
    </div>
  );
}

function TruthNote({ title, detail }: { title: string; detail: string }) {
  return (
    <article className="flex items-start gap-2 rounded-lg border border-[#b7c3ce] bg-white p-3">
      <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden />
      <div><p className="text-[9px] font-bold text-[#162536]">{title}</p><p className="mt-1 text-[8px] leading-3.5 text-[#5d6b79]">{detail}</p></div>
    </article>
  );
}

function ArchitectureDetailDrawer({ component, onClose, onSelect }: { component: ArchitectureComponent; onClose: () => void; onSelect: (id: string) => void }) {
  const plane = PLANE_META[component.plane];
  const deployment = DEPLOYMENT_META[component.deployment];
  const connected = CONNECTIONS.filter((connection) => connection.source === component.id || connection.target === component.id);
  return (
    <div className="fixed inset-0 z-[70]" role="dialog" aria-modal="true" aria-labelledby="architecture-detail-title">
      <button type="button" aria-label="Close component details" onClick={onClose} className="absolute inset-0 bg-[#081725]/55 backdrop-blur-[1px]" />
      <aside className="absolute inset-y-0 right-0 w-full max-w-[520px] overflow-y-auto border-l border-[#9aa9b8] bg-white shadow-2xl">
        <header className="sticky top-0 z-10 border-b border-[#cbd5df] bg-white/95 px-5 py-4 backdrop-blur">
          <div className="flex items-start gap-3">
            <span className="grid size-12 shrink-0 place-items-center rounded-lg border border-[#cbd5df] bg-[#f7f9fb]">
              {component.icon ? <img src={component.icon} alt="" className="size-9" /> : <UsersRound className="size-6 text-[#173d5c]" aria-hidden />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-bold uppercase tracking-[0.13em]" style={{ color: plane.color }}>{plane.label} plane</p>
              <h2 id="architecture-detail-title" className="mt-1 text-lg font-bold leading-tight text-[#162536]">{component.label}</h2>
              <p className="mt-1 text-[10px] text-[#52626f]">{component.service}</p>
              <span className={`mt-2 inline-flex rounded-full border px-2 py-1 text-[8px] font-bold uppercase tracking-wide ${deployment.className}`}>{deployment.label}</span>
            </div>
            <button type="button" onClick={onClose} aria-label="Close details" className="grid size-10 shrink-0 place-items-center rounded-md border border-[#cbd5df] text-[#536575] hover:bg-[#f2f5f7]"><X className="size-4" aria-hidden /></button>
          </div>
        </header>

        <div className="p-5">
          <div className="mb-4 rounded-lg border border-[#cbd5df] bg-[#f8fafc] p-3 text-[9.5px] leading-4 text-[#52626f]">
            This drawer describes the source-controlled service contract. Confirm current deployment and execution through stack outputs and retained runtime receipts.
          </div>
          <p className="text-sm leading-6 text-[#4e5f70]">{component.summary}</p>
          <dl className="mt-5 grid gap-3 sm:grid-cols-3">
            <DrawerDetail label="Receives" value={component.receives} />
            <DrawerDetail label="Processing" value={component.processing} />
            <DrawerDetail label="Emits" value={component.emits} />
          </dl>
          <dl className="mt-3 space-y-3">
            <DrawerDetail label="Scale" value={component.scaling} icon={<Boxes className="size-3.5" aria-hidden />} />
            <DrawerDetail label="Resilience" value={component.resilience} icon={<CheckCircle2 className="size-3.5" aria-hidden />} />
            <DrawerDetail label="Security boundary" value={component.security} icon={<ShieldCheck className="size-3.5" aria-hidden />} />
            <DrawerDetail label="Evidence retained" value={component.evidence} icon={<FileCheck2 className="size-3.5" aria-hidden />} />
          </dl>

          {connected.length > 0 ? (
            <section className="mt-5 border-t border-[#cbd5df] pt-4" aria-label="Connected architecture flows">
              <p className="text-[9px] font-bold uppercase tracking-[0.13em] text-[#52626f]">Connected flows</p>
              <div className="mt-2 space-y-2">
                {connected.map((connection) => {
                  const otherId = connection.source === component.id ? connection.target : connection.source;
                  const other = COMPONENTS.find((candidate) => candidate.id === otherId);
                  return (
                    <button key={connection.id} type="button" onClick={() => onSelect(otherId)} className="flex min-h-11 w-full items-center gap-2 rounded-md border border-[#cbd5df] bg-[#f8fafc] px-3 text-left text-[9px] text-[#5d6b79] hover:border-[#173d5c] hover:bg-[#edf4f9]">
                      <span className="size-2 shrink-0 rounded-full" style={{ background: FLOW_META[connection.kind].color }} />
                      <span className="min-w-0 flex-1">{connection.label}</span>
                      <ArrowRight className="size-3 shrink-0 text-[#173d5c]" aria-hidden />
                      <span className="max-w-36 truncate font-bold text-[#162536]">{other?.label ?? otherId}</span>
                    </button>
                  );
                })}
              </div>
            </section>
          ) : null}

          {component.docsUrl ? (
            <a href={component.docsUrl} target="_blank" rel="noreferrer" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-md border border-[#cbd5df] bg-white px-3 text-xs font-bold text-[#173d5c] hover:bg-[#f2f5f7]">
              Open official AWS documentation <ExternalLink className="size-3.5" aria-hidden />
            </a>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function DrawerDetail({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded-lg border border-[#d3dbe3] bg-[#f8fafc] p-3">
      <dt className="flex items-center gap-1.5 text-[8.5px] font-bold uppercase tracking-[0.12em] text-[#52626f]">{icon}{label}</dt>
      <dd className="mt-1.5 text-[10px] leading-4 text-[#4e5f70]">{value}</dd>
    </div>
  );
}

export default OverallArchitectureMap;
