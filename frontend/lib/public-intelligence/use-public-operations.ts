"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getContinuousPublicAcquisitionApi,
  getPublicAcquisitionsApi,
  startContinuousPublicAcquisitionApi,
  stopContinuousPublicAcquisitionApi,
  type ContinuousPublicAcquisitionControl,
  type PublicAcquisitionList,
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { publicOperationsSummary } from "./operations";
import {
  PUBLIC_OPERATIONS_AUTH_ERROR,
  publicOperationsAuthState,
} from "./public-operations-auth";

const DEFAULT_REFRESH_MS = 10_000;

export function usePublicOperations(refreshMs = DEFAULT_REFRESH_MS) {
  const auth = useAppAuth();
  const [data, setData] = useState<PublicAcquisitionList | null>(null);
  const [control, setControl] = useState<ContinuousPublicAcquisitionControl | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [controlling, setControlling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const mounted = useRef(true);
  const authState = publicOperationsAuthState(auth);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(async (silent = false) => {
    if (!auth.idToken) {
      if (!mounted.current) return;
      setLoading(auth.isLoading);
      setRefreshing(false);
      if (!auth.isLoading) setError(PUBLIC_OPERATIONS_AUTH_ERROR);
      return;
    }
    if (!silent) setRefreshing(true);
    try {
      const [nextData, nextControl] = await Promise.all([
        getPublicAcquisitionsApi(),
        getContinuousPublicAcquisitionApi(),
      ]);
      if (!mounted.current) return;
      setData(nextData);
      setControl(nextControl);
      setLastRefreshedAt(new Date().toISOString());
      setError(null);
    } catch (cause) {
      if (!mounted.current) return;
      setError(cause instanceof Error ? cause.message : "Live public evidence is unavailable.");
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [auth.idToken, auth.isLoading]);

  useEffect(() => {
    if (authState === "waiting") {
      setLoading(true);
      setError(null);
      return;
    }
    if (authState === "unavailable") {
      setData(null);
      setControl(null);
      setLoading(false);
      setRefreshing(false);
      setControlling(false);
      setLastRefreshedAt(null);
      setError(PUBLIC_OPERATIONS_AUTH_ERROR);
      return;
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(true), Math.max(5_000, refreshMs));
    return () => window.clearInterval(timer);
  }, [authState, refresh, refreshMs]);

  const setContinuous = useCallback(async (enabled: boolean) => {
    if (authState !== "ready") {
      setControlling(false);
      setError(PUBLIC_OPERATIONS_AUTH_ERROR);
      return;
    }
    setControlling(true);
    setError(null);
    try {
      const next = enabled
        ? await startContinuousPublicAcquisitionApi()
        : await stopContinuousPublicAcquisitionApi();
      setControl(next);
      await refresh(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The acquisition control did not update.");
    } finally {
      setControlling(false);
    }
  }, [authState, refresh]);

  const summary = useMemo(() => publicOperationsSummary(data), [data]);

  return {
    data,
    control,
    summary,
    loading,
    refreshing,
    controlling,
    error,
    lastRefreshedAt,
    refresh,
    setContinuous,
  };
}
