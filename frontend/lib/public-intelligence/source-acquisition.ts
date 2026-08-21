export type SourceAcquisitionState =
  | "collected_public"
  | "gated_commercial"
  | "gated_government"
  | "excluded";

export type SourceAcquisitionGroup = {
  id: string;
  label: string;
  state: SourceAcquisitionState;
  statusLabel: string;
  summary: string;
  items: readonly string[];
  activation: string;
  boundary: string;
};

export const COLLECTED_PUBLIC_SOURCE_COUNT = 12;
export const COLLECTED_PUBLIC_RECORD_COUNT = 177_503;

export const COLLECTED_PUBLIC_SOURCE_NAMES = [
  "USAspending",
  "SBIR and STTR",
  "Grants.gov",
  "SAM.gov",
  "DataCite",
  "Crossref",
  "OpenAlex",
  "PubMed",
  "OSTI.GOV",
  "USPTO PatentsView",
  "Federal Register",
  "Official ONR website index",
] as const;

export const SOURCE_ACQUISITION_GROUPS: readonly SourceAcquisitionGroup[] = [
  {
    id: "collected-public",
    label: "Collected public evidence",
    state: "collected_public",
    statusLabel: "Collected",
    summary: `${COLLECTED_PUBLIC_RECORD_COUNT.toLocaleString("en-US")} minimized records across ${COLLECTED_PUBLIC_SOURCE_COUNT} public source families.`,
    items: COLLECTED_PUBLIC_SOURCE_NAMES,
    activation: "Active in the governed snapshot with source URL, retrieval time, digest, schema version, and collection state.",
    boundary: "Public evidence supports portfolio analysis. It is not authoritative ONR operational truth.",
  },
  {
    id: "gated-commercial",
    label: "Licensed and commercial evidence",
    state: "gated_commercial",
    statusLabel: "Not collected",
    summary: "Declared acquisition categories that require an approved commercial source and license.",
    items: [
      "Startup investment intelligence",
      "Company ownership, profile, and financial intelligence",
      "Informal literature, commercial news, and market research",
    ],
    activation: "Requires Government-provided or approved licensing, API or export rights, data-use review, and retention and redistribution rules.",
    boundary: "No vendor has been selected and no licensed commercial records are in the current corpus.",
  },
  {
    id: "gated-government",
    label: "Government-furnished evidence",
    state: "gated_government",
    statusLabel: "Not connected or collected",
    summary: "Declared integration targets that require source-owner authorization and an approved Government transfer path.",
    items: [
      "Advana",
      "Pulse",
      "Restricted DTIC collections",
      "Navy budget SharePoint materials",
      "Structured Government acquisition and scientific reports",
      "Unstructured Government reports and documents",
    ],
    activation: "Requires Government-furnished access, a data-use agreement, distribution or CUI review, an approved transfer, and source-specific schema and rights review.",
    boundary: "No live Advana, Pulse, restricted DTIC, Navy SharePoint, or Government report connection is claimed, and no records from these sources are in the current corpus.",
  },
  {
    id: "excluded-restricted",
    label: "Restricted opportunity material",
    state: "excluded",
    statusLabel: "Intentionally excluded",
    summary: "Protected opportunity documents remain outside the public evidence boundary.",
    items: [
      "Restricted opportunity documents, controlled attachments, and access-labeled notices",
    ],
    activation: "Would require explicit source-owner authorization, distribution review, and an approved Government processing boundary.",
    boundary: "Public opportunity metadata is collected, but protected attachments and controlled documents are not fetched, indexed, embedded, or used for training.",
  },
] as const;
