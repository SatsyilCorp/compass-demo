import { classifyDocument, type ClassificationResult } from "../mlops/demo-model";

export const MAX_DOCUMENT_BYTES = 15 * 1024 * 1024;

export const DOCUMENT_MEDIA_TYPES = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  txt: "text/plain",
  md: "text/markdown",
  csv: "text/csv",
  json: "application/json",
  jsonl: "application/x-ndjson",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  xml: "application/xml",
} as const;

export type DocumentMediaType = (typeof DOCUMENT_MEDIA_TYPES)[keyof typeof DOCUMENT_MEDIA_TYPES];
export type IntakeStageId =
  | "hash"
  | "upload"
  | "detect"
  | "bronze"
  | "extract"
  | "quality"
  | "classify"
  | "gold";

export type IntakeStage = {
  id: IntakeStageId;
  label: string;
  system: string;
  detail: string;
};

export type LocalDocumentReceipt = {
  runId: string;
  fileName: string;
  mediaType: DocumentMediaType;
  sizeBytes: number;
  sha256: string;
  shape: "unstructured" | "records" | "workbook";
  qualityScore: number;
  classification: ClassificationResult;
  stages: IntakeStage[];
  mode: "bounded_browser_replay";
};

const EXTENSION_MEDIA = new Map<string, DocumentMediaType>(
  Object.entries(DOCUMENT_MEDIA_TYPES).map(([extension, media]) => [extension, media]),
);

export function mediaTypeForFile(fileName: string, browserType = ""): DocumentMediaType | null {
  const extension = fileName.toLowerCase().split(".").pop() ?? "";
  const expected = EXTENSION_MEDIA.get(extension) ?? null;
  if (!expected) return null;
  if (!browserType || browserType === "application/octet-stream") return expected;
  if (browserType === expected) return expected;
  if (extension === "jsonl" && browserType === "application/json") return expected;
  if (extension === "xml" && browserType === "text/xml") return expected;
  return null;
}

export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

export function intakeShape(mediaType: DocumentMediaType): LocalDocumentReceipt["shape"] {
  if (mediaType === DOCUMENT_MEDIA_TYPES.xlsx) return "workbook";
  const recordMedia: readonly DocumentMediaType[] = [DOCUMENT_MEDIA_TYPES.csv, DOCUMENT_MEDIA_TYPES.json, DOCUMENT_MEDIA_TYPES.jsonl];
  if (recordMedia.includes(mediaType)) return "records";
  return "unstructured";
}

export function validateDocument(file: Pick<File, "name" | "size" | "type">): string | null {
  if (!mediaTypeForFile(file.name, file.type)) return "Use PDF, DOCX, TXT, Markdown, CSV, JSON, JSONL, XLSX, or XML with a matching media type.";
  if (file.size < 1) return "The selected document is empty.";
  if (file.size > MAX_DOCUMENT_BYTES) return "The selected document exceeds the 15 MiB demonstration bound.";
  return null;
}

const LIVE_STAGE_INDEX: Readonly<Record<string, number>> = {
  "browser-upload": 1,
  inspect: 4,
  "bronze-inspected": 4,
  "quality-gate": 5,
  curate: 6,
  "gold-published": 7,
  quarantine: 5,
};

export function liveDocumentStageIndex(stage: string, status: string): number {
  if (status === "completed" || status === "curated") return 7;
  if (status === "quarantined") return stage === "inspect" ? 4 : 5;
  return LIVE_STAGE_INDEX[stage] ?? 2;
}

export function buildLocalReceipt(input: {
  fileName: string;
  mediaType: DocumentMediaType;
  sizeBytes: number;
  sha256: string;
  previewText: string;
}): LocalDocumentReceipt {
  const classification = classifyDocument(input.previewText, input.fileName);
  const shape = intakeShape(input.mediaType);
  const schemaDetail = shape === "records" ? "Record fields and compatible variations inferred" : shape === "workbook" ? "Workbook sheets and column headers profiled" : "Text and document metadata extracted";
  const qualityScore = classification.reviewRequired ? 88 : 98;
  return {
    runId: `doc-${input.sha256.slice(0, 16)}`,
    fileName: input.fileName,
    mediaType: input.mediaType,
    sizeBytes: input.sizeBytes,
    sha256: input.sha256,
    shape,
    qualityScore,
    classification,
    mode: "bounded_browser_replay",
    stages: [
      { id: "hash", label: "Validate and hash", system: "Compass browser", detail: "Extension, media type, size, synthetic marking, and SHA-256 verified" },
      { id: "upload", label: "Land source", system: "S3 incoming", detail: "Immutable source path and upload receipt prepared" },
      { id: "detect", label: "Detect event", system: "EventBridge", detail: "Object-created event correlated to the intake run" },
      { id: "bronze", label: "Retain Bronze", system: "S3 Bronze", detail: "Original bytes and extraction metadata retained for replay" },
      { id: "extract", label: "Extract and infer", system: "Document adapter", detail: schemaDetail },
      { id: "quality", label: "Apply quality gate", system: "Step Functions", detail: `${qualityScore}% quality score with blocking and advisory results` },
      { id: "classify", label: "Classify document", system: "Champion model", detail: `${classification.displayLabel} at ${Math.round(classification.confidence * 100)}% confidence` },
      { id: "gold", label: "Publish Gold", system: "Governed catalog", detail: classification.reviewRequired ? "Low-confidence record routed to human review" : "Classification and lineage published for decision support" },
    ],
  };
}

export function previewTextForBytes(mediaType: DocumentMediaType, bytes: ArrayBuffer): string {
  const textualMedia: readonly DocumentMediaType[] = [DOCUMENT_MEDIA_TYPES.txt, DOCUMENT_MEDIA_TYPES.md, DOCUMENT_MEDIA_TYPES.csv, DOCUMENT_MEDIA_TYPES.json, DOCUMENT_MEDIA_TYPES.jsonl, DOCUMENT_MEDIA_TYPES.xml];
  if (textualMedia.includes(mediaType)) {
    return new TextDecoder().decode(bytes.slice(0, 256_000));
  }
  return "";
}
