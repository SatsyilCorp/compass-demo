"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  Boxes,
  CheckCircle2,
  ChevronRight,
  CloudCog,
  Code2,
  ExternalLink,
  FileCode2,
  GitBranch,
  GitCommitHorizontal,
  LockKeyhole,
  Network,
  PackageCheck,
  Play,
  RefreshCcw,
  RotateCcw,
  ScanSearch,
  ShieldCheck,
  TerminalSquare,
  Workflow,
  type LucideIcon,
} from "lucide-react";

type DeliveryTab = "pipeline" | "iac" | "security" | "recovery";
type GateState = "pass" | "approval" | "deploy";

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
const SOURCE_REVISION = process.env.NEXT_PUBLIC_SOURCE_REVISION ?? "local candidate";

const GATES: Gate[] = [
  { id: "source", label: "Source integrity", detail: "Check out the reviewed commit, enforce ASCII content policy, and reject committed credentials.", command: "gitleaks detect --no-banner --redact", evidence: ".github/workflows/quality.yml", state: "pass", icon: GitCommitHorizontal },
  { id: "sast", label: "SAST and dependency", detail: "Analyze application code, audit locked dependencies, and generate a software bill of materials.", command: "semgrep ci && pip-audit && pnpm audit --prod", evidence: "artifacts/security/sbom.spdx.json", state: "pass", icon: ScanSearch },
  { id: "iac", label: "IaC and STIG policy", detail: "Validate Terraform and SAM, scan misconfiguration, and evaluate the demonstrable STIG control profile.", command: "terraform validate && checkov && cfn-guard validate", evidence: "infra/policy/", state: "pass", icon: FileCode2 },
  { id: "contracts", label: "Data and model contracts", detail: "Prove identity, quality, lineage, document, model, approval, export, and migration invariants.", command: "pytest -q scripts/tests src/common/tests src/functions/*/tests", evidence: "src/functions/*/tests", state: "pass", icon: PackageCheck },
  { id: "browser", label: "Build and browser smoke", detail: "Typecheck, build the static portal, then exercise responsive accessibility and the seven-element route set.", command: "pnpm typecheck && pnpm build && pnpm test:e2e", evidence: "frontend/playwright-report", state: "pass", icon: Play },
  { id: "approval", label: "Environment approval", detail: "Bind the exact commit, plan digest, evidence bundle, and reviewer decision before promotion.", command: "github environment: demo", evidence: "Delivery Receipt approval", state: "approval", icon: LockKeyhole },
  { id: "deploy", label: "OIDC deployment", detail: "Assume a short-lived AWS role, deploy the reviewed change set, run DAST and smoke checks, then retain the receipt.", command: "sam deploy --no-fail-on-empty-changeset", evidence: "Delivery Receipt terminal state", state: "deploy", icon: CloudCog },
];

const TABS: { id: DeliveryTab; label: string; icon: LucideIcon }[] = [
  { id: "pipeline", label: "Golden pipeline", icon: Workflow },
  { id: "iac", label: "Infrastructure plan", icon: Boxes },
  { id: "security", label: "Security and STIG", icon: ShieldCheck },
  { id: "recovery", label: "Recovery and rollback", icon: RefreshCcw },
];

const IAC_MODULES = [
  ["Edge and identity", "CloudFront, WAF, Cognito, API Gateway", "Public request and user trust boundary"],
  ["Application control", "Lambda, Step Functions, EventBridge", "Bounded orchestration and policy"],
  ["Document data plane", "S3, Kinesis, SQS, Textract adapters", "Bronze, Silver, Gold, and quarantine"],
  ["Model operations", "SageMaker Pipeline, Registry, Monitor", "Train, validate, approve, deploy, and drift"],
  ["Governed data", "Aurora, DynamoDB, Glue, Athena", "Policy, receipts, catalog, and serving"],
  ["Evidence and operations", "CloudWatch, CloudTrail, KMS, Backup", "Health, audit, recovery, and cost"],
];

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
              <span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/70">Commit-bound evidence</span>
            </div>
            <h2 className="mt-3 text-2xl font-bold">Golden delivery path</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">One reviewed revision moves through source, security, data, model, browser, approval, deployment, and runtime gates. Every transition produces a Delivery Receipt instead of relying on a verbal claim.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            <HeroMetric label="Revision" value={SOURCE_REVISION.slice(0, 12)} icon={GitCommitHorizontal} />
            <HeroMetric label="Quality gates" value={String(GATES.length)} icon={BadgeCheck} />
            <HeroMetric label="Long-lived keys" value="None" icon={LockKeyhole} />
          </div>
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
                <a href={`${REPOSITORY}/actions`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Open live Actions <ExternalLink className="size-3.5" aria-hidden /></a>
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
              <div className="mt-3 rounded-lg border border-border bg-white p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Retained evidence</p><p className="mt-1 break-all font-mono text-[10px] text-text-muted">{gate.evidence}</p></div>
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
  return <div className="p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Terraform plus SAM</p><h3 className="mt-1 text-lg font-bold text-text-strong">Inspectable infrastructure modules</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">Terraform defines the account and integration foundation. SAM defines the event-driven application. Both are validated from the same commit and cannot bypass the deployment approval.</p></div><a href={`${REPOSITORY}/tree/main/infra/terraform`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Open Terraform <ExternalLink className="size-3.5" aria-hidden /></a></div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{IAC_MODULES.map(([title, resources, purpose], index) => <article key={title} className="rounded-lg border border-border bg-white p-4"><div className="flex items-center justify-between"><span className="grid size-8 place-items-center rounded-md bg-gov-primary-lighter font-mono text-xs font-bold text-gov-primary">{String(index + 1).padStart(2, "0")}</span><ChevronRight className="size-4 text-text-subtle" aria-hidden /></div><h4 className="mt-3 text-sm font-bold text-text-strong">{title}</h4><p className="mt-1 text-[10px] font-semibold text-gold-ink">{resources}</p><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{purpose}</p></article>)}</div></div>;
}

function SecurityEvidence() {
  const controls = [
    ["Source", "Secret scanning, signed review context, branch and environment protection"],
    ["Application", "SAST, dependency audit, SBOM, unit, contract, browser, and DAST checks"],
    ["Infrastructure", "Terraform, CloudFormation, Checkov, cfn-lint, and cfn-guard policy"],
    ["STIG profile", "Traceable automated checks plus manual control inheritance and applicability evidence"],
    ["Runtime", "WAF, CloudTrail, CloudWatch, GuardDuty, Security Hub, KMS, and immutable receipts"],
    ["Promotion", "Short-lived OIDC identity, reviewed change set, smoke test, and rollback gate"],
  ];
  return <div className="p-5"><div className="rounded-lg border border-warn/30 bg-warn-soft p-4"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden /><div><p className="text-xs font-bold text-text-strong">Security evidence, not accreditation</p><p className="mt-1 text-xs leading-5 text-text-muted">These automated checks demonstrate familiarity and implementation discipline. They do not claim an RMF authorization, IL5 accreditation, or a complete applicable STIG checklist for an unknown target boundary.</p></div></div></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{controls.map(([title, detail]) => <article key={title} className="rounded-lg border border-border bg-white p-4"><ShieldCheck className="size-5 text-success" aria-hidden /><h4 className="mt-3 text-sm font-bold text-text-strong">{title}</h4><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{detail}</p></article>)}</div></div>;
}

function RecoveryEvidence() {
  return <div className="p-5"><div className="grid gap-4 lg:grid-cols-3"><RecoveryCard label="Proposed portal RTO" value="60 minutes" detail="Subject to discovery, dependency mapping, and Government approval." /><RecoveryCard label="Proposed decision-data RPO" value="15 minutes" detail="Versioned objects and managed backups support the target pattern." /><RecoveryCard label="Exercise status" value="Pattern ready" detail="No production disaster recovery result is claimed until an approved game day is executed." /></div><div className="mt-5 grid gap-3 md:grid-cols-2"><RecoveryStep number="1" title="Protect and observe" detail="Multi-AZ managed services, versioned immutable objects, queue durability, backup policy, and synthetic health probes." /><RecoveryStep number="2" title="Rebuild from source" detail="Reapply Terraform and SAM in the recovery region using reviewed configuration and short-lived deployment identity." /><RecoveryStep number="3" title="Restore and reconcile" detail="Restore control data, replay immutable manifests, redrive queues, and verify hashes, counts, policy, and model versions." /><RecoveryStep number="4" title="Shift and learn" detail="Move traffic through controlled DNS or distribution configuration, measure objectives, retain evidence, and close corrective actions." /></div></div>;
}

function HeroMetric({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) {
  return <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3"><Icon className="size-4 text-gold-light" aria-hidden /><p className="mt-2 text-[9px] font-bold uppercase tracking-wide text-white/45">{label}</p><p className="mt-1 break-all font-mono text-xs font-bold text-white/85">{value}</p></div>;
}

function GateState({ state }: { state: GateState }) {
  if (state === "pass") return <span className="inline-flex items-center gap-1 rounded-full border border-success/25 bg-success-soft px-2 py-0.5 text-[8px] font-bold uppercase text-success"><CheckCircle2 className="size-2.5" aria-hidden /> gate</span>;
  if (state === "approval") return <span className="rounded-full border border-warn/30 bg-warn-soft px-2 py-0.5 text-[8px] font-bold uppercase text-warn">review</span>;
  return <span className="rounded-full border border-info/30 bg-info-soft px-2 py-0.5 text-[8px] font-bold uppercase text-info">deploy</span>;
}

function RecoveryCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="rounded-lg border border-border bg-white p-4"><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-2 text-xl font-bold text-gov-primary">{value}</p><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{detail}</p></article>;
}

function RecoveryStep({ number, title, detail }: { number: string; title: string; detail: string }) {
  return <article className="flex gap-3 rounded-lg border border-border bg-white p-4"><span className="grid size-8 shrink-0 place-items-center rounded-md bg-gov-primary text-xs font-bold text-white">{number}</span><div><h4 className="text-sm font-bold text-text-strong">{title}</h4><p className="mt-1 text-[10.5px] leading-5 text-text-muted">{detail}</p></div></article>;
}
