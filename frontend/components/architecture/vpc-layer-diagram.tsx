import type { ReactNode } from "react";
import { ArrowDown, ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";

type ServiceCardProps = {
  label: string;
  service: string;
  icon: string;
  note?: string;
  tone?: "default" | "public" | "private" | "data";
};

const TONE: Record<NonNullable<ServiceCardProps["tone"]>, string> = {
  default: "border-border bg-white",
  public: "border-info/30 bg-info-soft/45",
  private: "border-gov-primary/30 bg-gov-primary-lighter/55",
  data: "border-success/30 bg-success-soft/50",
};

export function VpcLayerDiagram() {
  return (
    <section className="space-y-4" aria-label="AWS VPC and network layers">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1.2fr)_auto_minmax(0,1fr)] lg:items-stretch">
        <BoundaryBlock label="Users and public sources" detail="Outside AWS account trust">
          <ServiceCard label="Mission users" service="Browser over HTTPS" icon="/aws-icons/iam.svg" />
          <ServiceCard label="Public sources" service="USAspending and approved feeds" icon="/aws-icons/internet-gateway.svg" />
        </BoundaryBlock>
        <FlowArrow label="HTTPS" />
        <BoundaryBlock label="AWS edge and identity" detail="Managed services outside the customer VPC" accent>
          <div className="grid gap-2 sm:grid-cols-2">
            <ServiceCard label="Request screening" service="AWS WAF" icon="/aws-icons/waf.svg" tone="public" />
            <ServiceCard label="Web delivery" service="CloudFront and private S3 origin" icon="/aws-icons/cloudfront.svg" tone="public" />
            <ServiceCard label="User identity" service="Amazon Cognito" icon="/aws-icons/cognito.svg" tone="public" />
            <ServiceCard label="Protected API" service="API Gateway with JWT authorizer" icon="/aws-icons/api-gateway.svg" tone="public" />
          </div>
        </BoundaryBlock>
        <FlowArrow label="JWT and service invocation" />
        <BoundaryBlock label="AWS regional services" detail="Managed service plane outside the customer VPC">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
            <ServiceCard label="Event orchestration" service="EventBridge, Step Functions, SQS" icon="/aws-icons/step-functions.svg" />
            <ServiceCard label="Data and model services" service="S3, DynamoDB, Kinesis, Bedrock, SageMaker" icon="/aws-icons/s3.svg" />
            <ServiceCard label="Keys and operations" service="KMS, Secrets Manager, CloudWatch" icon="/aws-icons/kms.svg" />
          </div>
        </BoundaryBlock>
      </div>

      <div className="flex items-center justify-center gap-3 text-center text-[9px] font-bold uppercase tracking-wide text-gov-primary" aria-hidden>
        <span className="h-px flex-1 bg-gov-primary/25" />
        <ArrowDown className="size-4" />
        Private application connections enter below
        <ArrowDown className="size-4" />
        <span className="h-px flex-1 bg-gov-primary/25" />
      </div>

      <section className="overflow-hidden rounded-2xl border-[3px] border-gov-primary bg-[#f5f9fc] shadow-card" aria-labelledby="deployed-vpc-heading">
        <header className="flex flex-col gap-3 bg-gov-primary px-5 py-4 text-white sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-lg border border-white/20 bg-white/10">
              <img src="/aws-icons/vpc.svg" alt="" className="size-8" />
            </span>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-gold-light">Deployed customer VPC</p>
              <h4 id="deployed-vpc-heading" className="mt-0.5 text-lg font-bold">10.42.0.0/16 across two availability zones</h4>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-[9px] font-bold uppercase tracking-wide">
            <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1">DNS enabled</span>
            <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1">No public database</span>
            <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1">KMS encrypted</span>
          </div>
        </header>

        <div className="space-y-4 p-4 sm:p-5">
          <NetworkLayer
            number="1"
            title="Public routing layer"
            description="Only routing infrastructure is public. Application functions and Aurora are not placed here."
          >
            <div className="grid gap-3 lg:grid-cols-[0.7fr_1fr_1fr]">
              <ServiceCard
                label="Internet gateway"
                service="0.0.0.0/0 on public route table"
                icon="/aws-icons/internet-gateway.svg"
                note="Attached to the VPC"
                tone="public"
              />
              <SubnetCard
                az="Availability Zone A"
                name="Public subnet A"
                cidr="10.42.0.0/24"
                status="Active egress"
              >
                <ServiceCard label="NAT gateway" service="One Elastic IP" icon="/aws-icons/nat-gateway.svg" note="Current cost-controlled deployment" tone="public" />
              </SubnetCard>
              <SubnetCard
                az="Availability Zone B"
                name="Public subnet B"
                cidr="10.42.1.0/24"
                status="Routing ready"
              >
                <div className="rounded-lg border border-dashed border-border bg-white/70 p-3">
                  <p className="text-[10px] font-bold text-text-strong">No application workload</p>
                  <p className="mt-1 text-[9.5px] leading-4 text-text-muted">Target HA adds a second NAT or replaces public egress with approved private endpoints.</p>
                </div>
              </SubnetCard>
            </div>
          </NetworkLayer>

          <NetworkLayer
            number="2"
            title="Private application and data layer"
            description="Database-touching Lambda functions and Aurora use private addresses in both zones. There is no direct internet route."
          >
            <div className="grid gap-3 lg:grid-cols-2">
              <SubnetCard
                az="Availability Zone A"
                name="Private subnet A"
                cidr="10.42.10.0/24"
                status="Private only"
                privateLayer
              >
                <div className="grid gap-2 sm:grid-cols-2">
                  <ServiceCard label="Application compute" service="Lambda network interfaces" icon="/aws-icons/lambda.svg" note="Application security group" tone="private" />
                  <ServiceCard label="Aurora writer" service="Serverless v2 PostgreSQL 16.9" icon="/aws-icons/aurora.svg" note="Database security group" tone="data" />
                </div>
              </SubnetCard>
              <SubnetCard
                az="Availability Zone B"
                name="Private subnet B"
                cidr="10.42.11.0/24"
                status="Private only"
                privateLayer
              >
                <div className="grid gap-2 sm:grid-cols-2">
                  <ServiceCard label="Application compute" service="Lambda network interfaces" icon="/aws-icons/lambda.svg" note="Application security group" tone="private" />
                  <ServiceCard label="Aurora reader" service="Managed HA replica" icon="/aws-icons/aurora.svg" note="Failover and read capacity" tone="data" />
                </div>
              </SubnetCard>
            </div>
          </NetworkLayer>

          <NetworkLayer
            number="3"
            title="Private service access and security policy"
            description="The private route table keeps high-volume AWS data paths private and uses the NAT only for services without a configured endpoint."
          >
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <ServiceCard label="S3 gateway endpoint" service="Private route table" icon="/aws-icons/s3.svg" note="No NAT required" tone="private" />
              <ServiceCard label="DynamoDB gateway endpoint" service="Private route table" icon="/aws-icons/dynamodb.svg" note="No NAT required" tone="private" />
              <ServiceCard label="Application security group" service="Controlled egress" icon="/aws-icons/vpc.svg" note="Network identity for Lambda" tone="private" />
              <ServiceCard label="Database security group" service="TCP 5432 from application SG only" icon="/aws-icons/aurora.svg" note="No CIDR ingress" tone="data" />
            </div>
          </NetworkLayer>

          <div className="grid gap-3 lg:grid-cols-3" aria-label="Network security invariants">
            <SecurityRule title="No direct inbound path" detail="CloudFront, Cognito, and API Gateway terminate public interactions before any private workload runs." />
            <SecurityRule title="No public database" detail="Aurora has PubliclyAccessible set to false and accepts PostgreSQL only from the application security group." />
            <SecurityRule title="Evidence at every seam" detail="API logs, workflow receipts, object versions, model runs, alarms, and release digests preserve the operating trace." />
          </div>
        </div>
      </section>

      <section className="rounded-xl border-2 border-dashed border-gold/50 bg-gold-soft/40 p-4" aria-labelledby="network-target-heading">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-[0.15em] text-gold-ink">Target production hardening</p>
            <h4 id="network-target-heading" className="mt-1 text-sm font-bold text-text-strong">Changes required for a Government IL4/IL5 landing zone</h4>
          </div>
          <span className="self-start rounded-full border border-gold/50 bg-white px-2.5 py-1 text-[8.5px] font-bold uppercase tracking-wide text-gold-ink">Target, not deployed</span>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <TargetControl text="CAP or BCAP and VDSS replace the current commercial edge for protected traffic." />
          <TargetControl text="NAT per zone or approved private and FIPS endpoints remove the current single-AZ egress dependency." />
          <TargetControl text="Network Firewall, VPC Flow Logs, central DNS, and deny-by-default egress feed Government monitoring." />
          <TargetControl text="Separate application, data and ML, security, log archive, identity, and delivery accounts enforce macro-segmentation." />
        </div>
      </section>
    </section>
  );
}

function BoundaryBlock({ label, detail, accent = false, children }: { label: string; detail: string; accent?: boolean; children: ReactNode }) {
  return (
    <section className={`rounded-xl border-2 p-3 ${accent ? "border-info/35 bg-info-soft/25" : "border-border bg-surface-2/65"}`}>
      <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-gov-primary">{label}</p>
      <p className="mt-0.5 text-[9.5px] leading-4 text-text-muted">{detail}</p>
      <div className="mt-3 space-y-2">{children}</div>
    </section>
  );
}

function FlowArrow({ label }: { label: string }) {
  return (
    <div className="hidden w-20 flex-col items-center justify-center text-center lg:flex" aria-label={label}>
      <span className="text-[8px] font-bold uppercase tracking-wide text-gov-primary">{label}</span>
      <span className="mt-2 flex w-full items-center" aria-hidden>
        <span className="h-px flex-1 bg-gov-primary/40" />
        <ArrowRight className="-ml-px size-4 text-gov-primary" />
      </span>
    </div>
  );
}

function ServiceCard({ label, service, icon, note, tone = "default" }: ServiceCardProps) {
  return (
    <article className={`flex min-w-0 items-start gap-2.5 rounded-lg border p-2.5 ${TONE[tone]}`}>
      <span className="grid size-9 shrink-0 place-items-center rounded-md border border-border/80 bg-white">
        <img src={icon} alt="" className="size-6 object-contain" />
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold leading-4 text-text-strong">{label}</p>
        <p className="text-[9px] leading-3.5 text-text-muted">{service}</p>
        {note ? <p className="mt-1 text-[8px] font-bold uppercase tracking-wide text-gov-primary">{note}</p> : null}
      </div>
    </article>
  );
}

function NetworkLayer({ number, title, description, children }: { number: string; title: string; description: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-white">
      <header className="flex items-start gap-3 border-b border-border bg-surface-2 px-4 py-3">
        <span className="grid size-7 shrink-0 place-items-center rounded-full bg-gov-primary text-[10px] font-bold text-white">{number}</span>
        <div>
          <h5 className="text-xs font-bold text-text-strong">{title}</h5>
          <p className="mt-0.5 text-[9.5px] leading-4 text-text-muted">{description}</p>
        </div>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function SubnetCard({ az, name, cidr, status, privateLayer = false, children }: { az: string; name: string; cidr: string; status: string; privateLayer?: boolean; children: ReactNode }) {
  return (
    <section className={`rounded-xl border-2 p-3 ${privateLayer ? "border-gov-primary/35 bg-gov-primary-lighter/25" : "border-info/30 bg-info-soft/20"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[8.5px] font-bold uppercase tracking-wide text-text-subtle">{az}</p>
          <h6 className="mt-0.5 text-[11px] font-bold text-text-strong">{name}</h6>
          <code className="mt-0.5 block text-[9px] text-gov-primary">{cidr}</code>
        </div>
        <span className="rounded-full border border-border bg-white px-2 py-0.5 text-[8px] font-bold uppercase tracking-wide text-text-muted">{status}</span>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function SecurityRule({ title, detail }: { title: string; detail: string }) {
  return (
    <article className="flex gap-3 rounded-lg border border-success/25 bg-success-soft/45 p-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-success text-white"><ShieldCheck className="size-4" aria-hidden /></span>
      <div><p className="text-[10px] font-bold text-text-strong">{title}</p><p className="mt-1 text-[9.5px] leading-4 text-text-muted">{detail}</p></div>
    </article>
  );
}

function TargetControl({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-gold/30 bg-white/80 p-3">
      <LockKeyhole className="mt-0.5 size-3.5 shrink-0 text-gold-ink" aria-hidden />
      <p className="text-[9.5px] leading-4 text-text-muted">{text}</p>
    </div>
  );
}
