import type { EvidenceMode } from "../evidence-mode";

export type PresenterStep = {
  element: string;
  title: string;
  route: string;
  target: string;
  proof: string;
  narration: string;
};

type PresenterStepDefinition = Omit<PresenterStep, "route" | "proof" | "narration"> & {
  routes: Record<EvidenceMode, string>;
  copy: Record<EvidenceMode, Pick<PresenterStep, "proof" | "narration">>;
};

const STEP_DEFINITIONS: PresenterStepDefinition[] = [
  {
    element: "1",
    title: "Secure access and policy scope",
    target: "00:00 to 03:30",
    routes: { live: "/dashboard/", rehearsal: "/rehearsal/dashboard/" },
    copy: {
      live: {
        proof: "Show the signed-in persona, protected public-data scope, masked funding behavior, and a denied unauthenticated route in the evidence notes.",
        narration: "Compass starts from identity. Every public-data request inherits the resolved organization scope and database policy context.",
      },
      rehearsal: {
        proof: "Show the signed-in persona, scoped synthetic rows, masked funding behavior, and the same deny-by-default route policy.",
        narration: "The rehearsal still starts from identity. Fixture access follows the resolved organization scope and never widens authorization.",
      },
    },
  },
  {
    element: "2",
    title: "Infrastructure and delivery evidence",
    target: "03:30 to 08:30",
    routes: { live: "/admin/pipeline/", rehearsal: "/admin/pipeline/" },
    copy: {
      live: {
        proof: "Show deployed revision, request receipt, service posture, workflow definition, source-controlled CI gates, and generated control evidence.",
        narration: "The environment, delivery gates, and control evidence are versioned together, so deployed proof can be regenerated from the reviewed source.",
      },
      rehearsal: {
        proof: "Show the source-controlled workflow, IaC, CI gates, and retained control artifacts, while distinguishing architecture proof from runtime fixture evidence.",
        narration: "Rehearsal uses the same reviewed delivery definitions, but only retained artifacts are claimed as proof on this path.",
      },
    },
  },
  {
    element: "3",
    title: "Automated intake and quality gate",
    target: "08:30 to 14:00",
    routes: { live: "/ingest/", rehearsal: "/rehearsal/ingest/" },
    copy: {
      live: {
        proof: "Inspect the public-source controller and one accepted authority receipt, or submit a PII-minimized public file and follow its protected AWS stages.",
        narration: "Named public inputs enter a governed path that retains source identity, validates quality, quarantines failures, and publishes only accepted evidence.",
      },
      rehearsal: {
        proof: "Submit a prepared synthetic file, follow each deterministic stage, and confirm that a failed quality gate publishes no curated rows.",
        narration: "A clearly labeled fixture rehearses normalization, quality, quarantine, and publication without representing an authority response.",
      },
    },
  },
  {
    element: "4",
    title: "Governed catalog and lineage",
    target: "14:00 to 18:30",
    routes: { live: "/catalog/", rehearsal: "/rehearsal/catalog/" },
    copy: {
      live: {
        proof: "Open an accepted public source product, inspect its hashes and quality inputs, then traverse the retained source-to-decision lineage.",
        narration: "Catalog, quality, and lineage read the same protected run receipts, keeping every public claim tied to its authority and capture.",
      },
      rehearsal: {
        proof: "Open the newest synthetic batch, inspect the deterministic score inputs, then traverse its fixture-bound lineage graph.",
        narration: "Catalog, quality, and lineage share one rehearsal run identifier and source hash, so the explanation remains repeatable and isolated.",
      },
    },
  },
  {
    element: "5",
    title: "Decision-support analytics",
    target: "18:30 to 23:30",
    routes: { live: "/analytics/", rehearsal: "/rehearsal/analytics/" },
    copy: {
      live: {
        proof: "Inspect current public-source deltas, champion classifier receipts, review rules, metrics, and the linked model version.",
        narration: "Analytics derives bounded decision signals from accepted public evidence and keeps model version, confidence, source, and review state visible.",
      },
      rehearsal: {
        proof: "Run deterministic topic analysis on the synthetic batch, inspect parameters and metrics, and show the retained recommendation receipt.",
        narration: "Rehearsal exercises the portable analytics contract over isolated fixtures with explicit parameters, metrics, and model-run evidence.",
      },
    },
  },
  {
    element: "6",
    title: "Executive decision brief",
    target: "23:30 to 30:30",
    routes: { live: "/dashboard/", rehearsal: "/rehearsal/dashboard/" },
    copy: {
      live: {
        proof: "Filter accepted public records, inspect changed values and citations, review a model flag, and open its exact operational lineage.",
        narration: "Leaders see what changed in retained public evidence, what needs review, and which source and model receipts support the next action.",
      },
      rehearsal: {
        proof: "Filter the synthetic portfolio, drill into governed fixture records, ask a cited question, and rehearse one approval exception.",
        narration: "The deterministic decision brief shows workflow behavior and technical drill-through without representing an operational portfolio decision.",
      },
    },
  },
  {
    element: "Strategic prompts",
    title: "Lifecycle, planning, and agility",
    target: "30:30 to 34:00",
    routes: { live: "/licenses/", rehearsal: "/rehearsal/licenses/" },
    copy: {
      live: {
        proof: "Inspect current source contracts, ownership, cadence, health, downstream model use, and portable replacement seams.",
        narration: "Compass connects evidence products to the source, stewardship, renewal, and portability decisions that keep the mission workflow available.",
      },
      rehearsal: {
        proof: "Use representative license fixtures to rehearse renewal evaluation, dependent datasets, utilization, and a clearly labeled planning scenario.",
        narration: "Representative policy records demonstrate the lifecycle workflow while remaining separate from an authoritative vendor inventory.",
      },
    },
  },
  {
    element: "7",
    title: "Portable preview and release boundary",
    target: "34:00 to 39:00",
    routes: { live: "/export/", rehearsal: "/rehearsal/export/" },
    copy: {
      live: {
        proof: "Create the browser-generated JSON or CSV preview, inspect source identity and its local checksum, then point to the disclosure that no server approval, delivery, audit record, or release receipt was created.",
        narration: "This screen proves open-format portability. A governed release remains a separate protected API workflow that must verify scope, apply approval policy, deliver the object, and return server evidence before we claim it executed.",
      },
      rehearsal: {
        proof: "Trigger the aggregation guard, rehearse four-eyes approval, and inspect the deterministic export fingerprint and audit receipt.",
        narration: "The rehearsal proves release policy and one-time approval behavior without claiming that a cloud file was delivered.",
      },
    },
  },
];

export function presenterStepsForMode(mode: EvidenceMode): PresenterStep[] {
  return STEP_DEFINITIONS.map((definition) => ({
    element: definition.element,
    title: definition.title,
    target: definition.target,
    route: definition.routes[mode],
    proof: definition.copy[mode].proof,
    narration: definition.copy[mode].narration,
  }));
}
