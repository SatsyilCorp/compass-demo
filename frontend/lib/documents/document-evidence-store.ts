import type { LocalDocumentReceipt } from "@/lib/documents/document-intake";

const STORAGE_KEY = "compass.document-evidence.v1";
const EVENT_NAME = "compass:document-evidence";

export function saveDocumentEvidence(receipt: LocalDocumentReceipt): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(receipt));
  window.dispatchEvent(new CustomEvent(EVENT_NAME));
}

export function readDocumentEvidence(): LocalDocumentReceipt | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as LocalDocumentReceipt;
    return value.mode === "bounded_browser_replay" && value.sha256.length === 64 ? value : null;
  } catch {
    return null;
  }
}

export function subscribeDocumentEvidence(listener: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(EVENT_NAME, listener);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(EVENT_NAME, listener);
  };
}
