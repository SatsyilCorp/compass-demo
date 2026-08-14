"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  Boxes,
  CloudCog,
  Code2,
  ExternalLink,
  FileCode2,
  GitCommitHorizontal,
  LockKeyhole,
  PackageCheck,
  Play,
  RefreshCcw,
  ScanSearch,
  ShieldCheck,
  TerminalSquare,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { deliveryEvidence, type DeliveryQualityStatus } from "./evidence-model";

type DeliveryTab = "pipeline" | "iac" | "security" | "recovery";
type GateState = "defined" | "approval" | "deploy";
type IacModuleState = "application-iac" | "conditional" | "target";

type Gate = {
  id: string;
  label: string;
  detail: string;
  command: string;
  evidence: string;
  state: GateState;
  icon: LucideIcon;
};

const REPOSITORY = "https://github.com/SatsyilCorp/compass-demo";
const DELIVERY_EVIDENCE = deliveryEvidence({
  sourceRevision: process.env.NEXT_PUBLIC_SOURCE_REVISION,
  qualityStatus: process.env.NEXT_PUBLIC_QUALITY_STATUS,
  qualityRunUrl: process.env.NEXT_PUBLIC_QUALITY_RUN_URL,
});

const GATES: Gate[] = [
  { id: "source", label: "Source integrity", detail: "Check out the reviewed commit, enforce ASCII content policy, and reject committed credentials.", command: "gitleaks detect --no-banner --redact", evidence: ".github/workflows/quality.yml", state: "defined", icon: GitCommitHorizontal },
  { id: "sast", label: "SAST and dependency", detail: "Run Bandit, audit locked dependencies, scan secrets, and emit the compass-sbom.cdx.json CycloneDX artifact.", command: "bandit -r src scripts -ll -ii && pip-audit --no-deps", evidence: ".github/workflows/devsecops.yml", state: "defined", icon: ScanSearch },
  { id: "iac", label: "IaC and STIG policy", detail: "Validate Terraform and SAM, then evaluate the demonstrable STIG control profile with CloudFormation Guard.", command: "terraform fmt -check -recursive && terraform validate && sam validate --lint && cfn-guard validate", evidence: "security/policies/compass.guard", state: "defined", icon: FileCode2 },
  { id: "contracts", label: "Data and model contracts", detail: "Prove identity, quality, lineage, document, model, approval, export, and migration invariants.", command: "pytest -q scripts/tests src/common/tests src/functions/*/tests", evidence: "src/functions/*/tests", state: "defined", icon: PackageCheck },
  { id: "browser", label: "Build and browser smoke", detail: "Typecheck, build the static portal, then exercise responsive accessibility and the seven-element route set.", command: "pnpm typecheck && pnpm build && pnpm test:e2e", evidence: "frontend/playwright-report", state: "defined", icon: Play },
  { id: "approval", label: "Environment approval", detail: "Bind the exact commit, plan digest, evidence bundle, and reviewer decision before promotion.", command: "github environment: demo", evidence: "Delivery Receipt approval", state: "approval", icon: LockKeyhole },
  { id: "deploy", label: "OIDC deployment", detail: "Assume a short-lived AWS role, deploy the reviewed change set, run DAST and smoke checks, then retain the receipt.", command: "sam deploy --no-fail-on-empty-changeset", evidence: "Delivery Receipt terminal state", state: "deploy", icon: CloudCog },
];

const TABS: { id: DeliveryTab; label: string; icon: LucideIcon }[] = [
  { id: "pipeline", label: "Golden pipeline", icon: Workflow },
  { id: "iac", label: "Infrastructure plan", icon: Boxes },
  { id: "security", label: "Security and STIG", icon: ShieldCheck },
  { id: "recovery", label: "Recovery and rollback", icon: RefreshCcw },
];

const IAC_MODULES: { title: string; resources: string; purpose: string; state: IacModuleState }[] = [
  { title: "Edge and identity", resources: "CloudFront, WAF, Cognito, API Gateway", purpose: "Application request and user trust controls declared in the SAM stack.", state: "application-iac" },
  { title: "Application control", resources: "Lambda, Step Functions, EventBridge", purpose: "Bounded orchestration, source schedules, and policy declared in application IaC.", state: "application-iac" },
  { title: "Document data plane", resources: "S3, Kinesis, SQS, Lambda document adapters", purpose: "Bronze, Silver, Gold, quarantine, and evidence paths declared without claiming a Textract deployment.", state: "application-iac" },
  { title: "Governed data", resources: "Aurora, DynamoDB, Glue, Athena", purpose: "Policy, receipts, catalog, and serving resources declared in the application stack.", state: "application-iac" },
  { title: "Model governance", resources: "Lambda classifier, Compass drift receipts, SageMaker Model Registry groups", purpose: "The application declares model registry and receipt controls. Current package state must come from an authenticated model receipt.", state: "application-iac" },
  { title: "Application evidence", resources: "CloudWatch, KMS, immutable application receipts", purpose: "Health, encryption, lineage, audit, and cost evidence declared in the application stack.", state: "application-iac" },
  { title: "SageMaker execution", resources: "Network-isolated training and Batch Transform", purpose: "Activates only with approved artifacts, execution configuration, and a retained SageMaker receipt. No Pipeline, Model Monitor, or endpoint is claimed.", state: "conditional" },
  { title: "Account security and recovery", resources: "CloudTrail, AWS Backup, GuardDuty, Security Hub", purpose: "Account-level, inherited, or target controls. They require separate current-environment evidence before any deployment claim.", state: "target" },
];

const IAC_STATE_META: Record<IacModuleState, { label: string; className: string }> = {
  "application-iac": { label: "Application IaC", className: "border-success/30 bg-success-soft text-success" },
  conditional: { label: "Conditional", className: "border-gold/40 bg-gold-soft text-gold-ink" },
  target: { label: "Account or target", className: "border-border bg-surface-2 text-text-muted" },
};

export function DeliveryControl() {
  const [tab, setTab] = useState<DeliveryTab>("pipeline");
  const [selectedGate, setSelectedGate] = useState(GATES[0].id);
  const gate = useMemo(() => GATES.find((item) => item.id === selectedGate) ?? GATES[0], [selectedGate]);
  const GateIcon = gate.icon;

  return (
    <div className="mt-6 space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card">
        <div className="compass-grid-overlay grid gap-5 px-5 py-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)] lg:px-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-gold-light">Element 2 of 7</span>
              <span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/70">Commit-bound definitions</span>
            </div>
            <h2 className="mt-3 text-2xl font-bold">Golden delivery path</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">The repository defines one path through source, security, data, model, browser, approval, deployment, and runtime gates. The build receipt below identifies the exact revision and current quality result when that evidence is available.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            <HeroMetric label="Revision" value={DELIVERY_EVIDENCE.revisionLabel} icon={GitCommitHorizontal} />
            <HeroMetric label="CI receipt" value={DELIVERY_EVIDENCE.qualityLabel} icon={BadgeCheck} />
            <HeroMetric label="Cloud auth definition" value="OIDC" icon={LockKeyhole} />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-white p-4 shadow-card sm:p-5" aria-label="Build-time deployment receipt">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Build-time deployment receipt</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <QualityReceiptState status={DELIVERY_EVIDENCE.qualityStatus} />
              <code className="break-all rounded-md border border-border bg-surface-2 px-2.5 py-1.5 font-mono text-[10px] text-text-muted">
                {DELIVERY_EVIDENCE.revision ?? "Exact deployed revision not recorded"}
              </code>
            </div>
            <p className="mt-2 max-w-4xl text-xs leading-5 text-text-muted">{DELIVERY_EVIDENCE.caveat}</p>
          </div>
          <a href={DELIVERY_EVIDENCE.qualityRunUrl ?? `${REPOSITORY}/actions`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">
            {DELIVERY_EVIDENCE.qualityRunUrl ? "Open exact quality run" : "Open Actions"} <ExternalLink className="size-3.5" aria-hidden />
          </a>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
        <div className="grid gap-2 border-b border-border bg-white p-3 sm:grid-cols-2 lg:grid-cols-4" role="tablist" aria-label="Delivery evidence views">
          {TABS.map((item) => {
            const Icon = item.icon;
            const active = item.id === tab;
            return <button key={item.id} type="button" role="tab" aria-selected={active} onClick={() => setTab(item.id)} className={`flex min-h-12 items-center gap-2 rounded-md border px-3 text-left text-xs font-bold ${active ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2"}`}><Icon className="size-4" aria-hidden /> {item.label}</button>;
          })}
        </div>

        {tab === "pipeline" ? (
          <div className="grid lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="border-b border-border p-4 lg:border-b-0 lg:border-r sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">CI/CD execution</p><h3 className="mt-1 text-lg font-bold text-text-strong">Secure promotion sequence</h3></div>
                <a href={DELIVERY_EVIDENCE.qualityRunUrl ?? `${REPOSITORY}/actions`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">{DELIVERY_EVIDENCE.qualityRunUrl ? "Open exact receipt" : "Open Actions"} <ExternalLink className="size-3.5" aria-hidden /></a>
              </div>
              <div className="mt-5 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {GATES.map((item, index) => {
                  const Icon = item.icon;
                  const active = item.id === gate.id;
                  return <button key={item.id} type="button" onClick={() => setSelectedGate(item.id)} className={`relative min-h-28 rounded-lg border p-3 text-left ${active ? "border-gov-primary bg-gov-primary-lighter shadow-soft" : "border-border bg-white hover:border-gov-primary/35"}`}><span className="flex items-center justify-between"><span className="grid size-8 place-items-center rounded-md bg-gov-primary text-white"><Icon className="size-4" aria-hidden /></span><GateState state={item.state} /></span><span className="mt-3 block text-xs font-bold text-text-strong">{index + 1}. {item.label}</span><span className="mt-1 line-clamp-2 block text-[9.5px] leading-4 text-text-muted">{item.detail}</span></button>;
                })}
              </div>
            </div>
            <aside className="bg-surface-2 p-5" aria-label="Selected delivery gate">
              <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-md bg-gov-primary text-white"><GateIcon className="size-5" aria-hidden /></span><div><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Selected gate</p><h3 className="text-sm font-bold text-text-strong">{gate.label}</h3></div></div>
              <p className="mt-4 text-xs leading-5 text-text-muted">{gate.detail}</p>
              <div className="mt-4 rounded-lg border border-border bg-[#061d2e] p-3 text-[#d8edf7]"><p className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-wide text-[#8db6ca]"><TerminalSquare className="size-3" aria-hidden /> Pipeline command</p><code className="mt-2 block break-all font-mono text-[10px] leading-5">{gate.command}</code></div>
              <div className="mt-3 rounded-lg border border-border bg-white p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Definition or receipt location</p><p className="mt-1 break-all font-mono text-[10px] text-text-muted">{gate.evidence}</p></div>
              <a href={`${REPOSITORY}/blob/main/${gate.evidence.replace(/\*\/tests$/, "")}`} target="_blank" rel="noreferrer" className="mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-gov-primary/25 bg-white text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Inspect source <Code2 className="size-3.5" aria-hidden /></a>
            </aside>
          </div>
        ) : null}

        {tab === "iac" ? <InfrastructurePlan /> : null}
        {tab === "security" ? <SecurityEvidence /> : null}
        {tab === "recovery" ? <RecoveryEvidence /> : null}
      </section>
    </div>
  );
}

function InfrastructurePlan() {
  return <div className="p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Terraform plus SAM</p><h3 className="mt-1 text-lg font-bold text-text-strong">Inspectable infrastructure modules</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">Terraform defines the account and integration foundation. SAM defines the event-driven application. These cards describe source-controlled intent, not current runtime proof. Stack outputs and retained receipts must verify the deployed environment.</p></div><a href={`${REPOSITORY}/tree/main/infra/terraform`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Open Terraform <ExternalLink className="size-3.5" aria-hidden /></a></div><div className="mt-4 flex flex-wrap gap-2" aria-label="Infrastructure evidence legend">{Object.values(IAC_STATE_META).map((state) => <span key={state.label} className={`rounded-full border px-2.5 py-1 text-[8.5px] font-bold uppercase tracking-wide ${state.className}`}>{state.label}</span>)}</div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">{IAC_MODULES.map((module, index) => { const state = IAC_STATE_META[module.state]; return <article key={module.title} className="rounded-lg border border-border bg-white p-4"><div className="flex items-center justify-between gap-2"><span className="grid size-8 place-items-center rounded-md bg-gov-primary-lighter font-mono text-xs font-bold text-gov-primary">{String(index + 1).padStart(2, "0")}</span><span className={`rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase tracking-wide ${state.className}`}>{state.label}</span></div><h4 className="mt-3 text-sm font-bold text-text-strong">{module.title}</h4><p className="mt-1 text-[10px] font-semibold text-gold-ink">{module.resources}</p><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{module.purpose}</p></article>; })}</div></div>;
}

function SecurityEvidence() {
  const controls = [
    ["Source", "Secret scanning, signed review context, branch and environment protection"],
    ["Application", "SAST, dependency audit, SBOM, unit, contract, browser, and DAST checks"],
    ["Infrastructure", "Terraform, CloudFormation, Checkov, cfn-lint, and cfn-guard policy"],
    ["STIG profile", "Traceable automated checks plus manual control inheritance and applicability evidence"],
    ["Application runtime", "WAF, CloudWatch, KMS, and immutable application receipts are declared in the application stack"],
    ["Account-level controls", "CloudTrail, GuardDuty, Security Hub, and AWS Backup are conditional, inherited, or target controls that require separate current-environment evidence"],
    ["Promotion", "Short-lived OIDC identity, reviewed change set, smoke test, and rollback gate"],
  ];
  return <div className="p-5"><div className="rounded-lg border border-warn/30 bg-warn-soft p-4"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden /><div><p className="text-xs font-bold text-text-strong">Security evidence, not accreditation</p><p className="mt-1 text-xs leading-5 text-text-muted">These automated checks demonstrate familiarity and implementation discipline. They do not claim an RMF authorization, IL5 accreditation, or a complete applicable STIG checklist for an unknown target boundary.</p></div></div></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{controls.map(([title, detail]) => <article key={title} className="rounded-lg border border-border bg-white p-4"><ShieldCheck className="size-5 text-success" aria-hidden /><h4 className="mt-3 text-sm font-bold text-text-strong">{title}</h4><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{detail}</p></article>)}</div></div>;
}

function RecoveryEvidence() {
  return <div className="p-5"><div className="grid gap-4 lg:grid-cols-3"><RecoveryCard label="Proposed portal RTO" value="60 minutes" detail="Subject to discovery, dependency mapping, and Government approval." /><RecoveryCard label="Proposed decision-data RPO" value="15 minutes" detail="Versioned objects, Aurora automated retention, and DynamoDB point-in-time recovery support the target pattern." /><RecoveryCard label="Exercise status" value="Pattern ready" detail="No production disaster recovery result is claimed until an approved game day is executed." /></div><div className="mt-5 grid gap-3 md:grid-cols-2"><RecoveryStep number="1" title="Protect and observe" detail="Multi-AZ managed services, versioned immutable objects, queue durability, service-native retention, point-in-time recovery, and health probes." /><RecoveryStep number="2" title="Rebuild from source" detail="Reapply Terraform and SAM in the recovery region using reviewed configuration and short-lived deployment identity." /><RecoveryStep number="3" title="Restore and reconcile" detail="Restore control data, replay immutable manifests, redrive queues, and verify hashes, counts, policy, and model versions." /><RecoveryStep number="4" title="Shift and learn" detail="Move traffic through controlled DNS or distribution configuration, measure objectives, retain evidence, and close corrective actions." /></div></div>;
}

function HeroMetric({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) {
  return <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3"><Icon className="size-4 text-gold-light" aria-hidden /><p className="mt-2 text-[9px] font-bold uppercase tracking-wide text-white/45">{label}</p><p className="mt-1 break-all font-mono text-xs font-bold text-white/85">{value}</p></div>;
}

function QualityReceiptState({ status }: { status: DeliveryQualityStatus }) {
  if (status === "success") return <span className="rounded-full border border-success/30 bg-success-soft px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-success">Verified success</span>;
  if (status === "failure") return <span className="rounded-full border border-danger/30 bg-danger-soft px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-danger">Failed</span>;
  if (status === "pending") return <span className="rounded-full border border-warn/30 bg-warn-soft px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-warn">Running</span>;
  return <span className="rounded-full border border-border bg-surface-2 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-text-muted">Not verified</span>;
}

function GateState({ state }: { state: GateState }) {
  if (state === "defined") return <span className="inline-flex items-center gap-1 rounded-full border border-info/25 bg-info-soft px-2 py-0.5 text-[8px] font-bold uppercase text-info"><FileCode2 className="size-2.5" aria-hidden /> defined</span>;
  if (state === "approval") return <span className="rounded-full border border-warn/30 bg-warn-soft px-2 py-0.5 text-[8px] font-bold uppercase text-warn">review</span>;
  return <span className="rounded-full border border-info/30 bg-info-soft px-2 py-0.5 text-[8px] font-bold uppercase text-info">deploy</span>;
}

function RecoveryCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="rounded-lg border border-border bg-white p-4"><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-2 text-xl font-bold text-gov-primary">{value}</p><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{detail}</p></article>;
}

function RecoveryStep({ number, title, detail }: { number: string; title: string; detail: string }) {
  return <article className="flex gap-3 rounded-lg border border-border bg-white p-4"><span className="grid size-8 shrink-0 place-items-center rounded-md bg-gov-primary text-xs font-bold text-white">{number}</span><div><h4 className="text-sm font-bold text-text-strong">{title}</h4><p className="mt-1 text-[10.5px] leading-5 text-text-muted">{detail}</p></div></article>;
}
