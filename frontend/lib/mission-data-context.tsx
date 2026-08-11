"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export const MISSION_DATA_STORAGE_KEY = "compass.mission-evidence.v1";
export const SCALE_RUN_ID_PATTERN = /^scale-[A-Za-z0-9-]+$/;

export type MissionDataSelection =
  | { kind: "curated" }
  | { kind: "scale"; runId: string };

export type MissionDataContextValue = {
  hydrated: boolean;
  selection: MissionDataSelection;
  selectCurated: () => void;
  selectScaleRun: (runId: string) => void;
};

const CURATED_SELECTION: MissionDataSelection = { kind: "curated" };

const MissionDataContext = createContext<MissionDataContextValue | null>(null);

function restoredSelection(raw: string | null): MissionDataSelection {
  if (!raw) return CURATED_SELECTION;
  try {
    const candidate = JSON.parse(raw) as unknown;
    if (!candidate || typeof candidate !== "object") return CURATED_SELECTION;
    const record = candidate as Record<string, unknown>;
    if (record.kind === "curated") return CURATED_SELECTION;
    if (
      record.kind === "scale" &&
      typeof record.runId === "string" &&
      SCALE_RUN_ID_PATTERN.test(record.runId)
    ) {
      return { kind: "scale", runId: record.runId };
    }
  } catch {
    // Invalid or legacy storage is not an evidence selection.
  }
  return CURATED_SELECTION;
}

export function MissionDataProvider({ children }: { children: React.ReactNode }) {
  const [selection, setSelection] = useState<MissionDataSelection>(CURATED_SELECTION);
  const [hydrated, setHydrated] = useState(false);
  const hydratedRef = useRef(false);
  const selectionBeforeHydrationRef = useRef<MissionDataSelection | null>(null);

  useEffect(() => {
    let restored = CURATED_SELECTION;
    try {
      restored = restoredSelection(window.sessionStorage.getItem(MISSION_DATA_STORAGE_KEY));
    } catch {
      // Storage can be unavailable in private browsing. Keep the safe default.
    }
    setSelection(selectionBeforeHydrationRef.current ?? restored);
    selectionBeforeHydrationRef.current = null;
    hydratedRef.current = true;
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.sessionStorage.setItem(MISSION_DATA_STORAGE_KEY, JSON.stringify(selection));
    } catch {
      // Selection remains valid for this mounted application even without storage.
    }
  }, [hydrated, selection]);

  const selectCurated = useCallback(() => {
    if (!hydratedRef.current) selectionBeforeHydrationRef.current = CURATED_SELECTION;
    setSelection(CURATED_SELECTION);
  }, []);

  const selectScaleRun = useCallback((runId: string) => {
    if (!SCALE_RUN_ID_PATTERN.test(runId)) {
      throw new Error("invalid_scale_run_id");
    }
    const next: MissionDataSelection = { kind: "scale", runId };
    if (!hydratedRef.current) selectionBeforeHydrationRef.current = next;
    setSelection(next);
  }, []);

  const value = useMemo<MissionDataContextValue>(
    () => ({ hydrated, selection, selectCurated, selectScaleRun }),
    [hydrated, selection, selectCurated, selectScaleRun],
  );

  return <MissionDataContext.Provider value={value}>{children}</MissionDataContext.Provider>;
}

export function useMissionDataContext(): MissionDataContextValue {
  const value = useContext(MissionDataContext);
  if (!value) {
    throw new Error("useMissionDataContext must be used inside MissionDataProvider");
  }
  return value;
}
