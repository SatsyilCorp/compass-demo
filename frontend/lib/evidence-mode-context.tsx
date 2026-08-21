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
import { usePathname } from "next/navigation";

import {
  DEFAULT_EVIDENCE_MODE,
  EVIDENCE_MODE_STORAGE_KEY,
  SINGLE_LIVE_MODE,
  evidenceModeForPath,
  parseEvidenceMode,
  persistEvidenceMode,
  readEvidenceMode,
  resolveInitialEvidenceMode,
  setRuntimeEvidenceMode,
  type EvidenceMode,
} from "@/lib/evidence-mode";

export type EvidenceModeContextValue = {
  hydrated: boolean;
  mode: EvidenceMode;
  selectMode: (mode: EvidenceMode) => void;
};

const EvidenceModeContext = createContext<EvidenceModeContextValue | null>(null);

export function EvidenceModeProvider({ children }: { children: React.ReactNode }) {
  if (SINGLE_LIVE_MODE) return <SingleLiveProvider>{children}</SingleLiveProvider>;
  return <SelectableProvider>{children}</SelectableProvider>;
}

/**
 * Single-mode presentation: the mode is a constant. `hydrated` still flips in
 * an effect so the AppShell prerender/first-paint sequencing stays identical
 * to the selectable provider - returning hydrated=true synchronously would
 * prerender the whole shell subtree.
 */
function SingleLiveProvider({ children }: { children: React.ReactNode }) {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setRuntimeEvidenceMode("live");
    setHydrated(true);
  }, []);

  const selectMode = useCallback((_next: EvidenceMode) => {
    // Mode selection is disabled in the single-mode presentation build.
  }, []);

  const value = useMemo<EvidenceModeContextValue>(
    () => ({ hydrated, mode: "live", selectMode }),
    [hydrated, selectMode],
  );

  return <EvidenceModeContext.Provider value={value}>{children}</EvidenceModeContext.Provider>;
}

function SelectableProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const [mode, setMode] = useState<EvidenceMode>(DEFAULT_EVIDENCE_MODE);
  const [hydrated, setHydrated] = useState(false);
  const hydrationComplete = useRef(false);
  const pathnameRef = useRef(pathname);

  useEffect(() => {
    pathnameRef.current = pathname;
    const routedMode = evidenceModeForPath(pathname);
    if (!hydrationComplete.current) {
      const restored = resolveInitialEvidenceMode(
        pathname,
        readEvidenceMode(window.localStorage),
      );
      setRuntimeEvidenceMode(restored);
      if (routedMode) persistEvidenceMode(restored, window.localStorage);
      setMode(restored);
      hydrationComplete.current = true;
      setHydrated(true);
      return;
    }

    if (routedMode) {
      setRuntimeEvidenceMode(routedMode);
      persistEvidenceMode(routedMode, window.localStorage);
      setMode(routedMode);
    }
  }, [pathname]);

  useEffect(() => {
    const synchronizeTabs = (event: StorageEvent) => {
      if (event.key !== EVIDENCE_MODE_STORAGE_KEY) return;
      const routedMode = evidenceModeForPath(pathnameRef.current);
      const next = routedMode ?? parseEvidenceMode(event.newValue);
      setRuntimeEvidenceMode(next);
      if (routedMode) persistEvidenceMode(routedMode, window.localStorage);
      setMode(next);
    };
    window.addEventListener("storage", synchronizeTabs);
    return () => window.removeEventListener("storage", synchronizeTabs);
  }, []);

  const selectMode = useCallback((next: EvidenceMode) => {
    setRuntimeEvidenceMode(next);
    persistEvidenceMode(next, window.localStorage);
    setMode(next);
  }, []);

  const routedMode = evidenceModeForPath(pathname);
  const effectiveMode = routedMode ?? mode;
  const effectiveHydrated = hydrated && (!routedMode || routedMode === mode);

  const value = useMemo<EvidenceModeContextValue>(
    () => ({ hydrated: effectiveHydrated, mode: effectiveMode, selectMode }),
    [effectiveHydrated, effectiveMode, selectMode],
  );

  return <EvidenceModeContext.Provider value={value}>{children}</EvidenceModeContext.Provider>;
}

/** Tolerant variant: null outside the provider (e.g. isolated tests). */
export function useEvidenceModeOptional(): EvidenceModeContextValue | null {
  return useContext(EvidenceModeContext);
}

export function useEvidenceMode(): EvidenceModeContextValue {
  const value = useContext(EvidenceModeContext);
  if (!value) throw new Error("useEvidenceMode must be used inside EvidenceModeProvider");
  return value;
}
