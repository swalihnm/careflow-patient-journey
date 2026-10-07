"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "./api";
import { useRole } from "./role-context";

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  forbidden: boolean;
  refetch: () => void;
}

export function useApi<T>(path: string | null, deps: unknown[] = []): UseApiResult<T> {
  const { role } = useRole();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setForbidden(false);

    apiFetch<T>(path, role)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 403) {
          setForbidden(true);
        } else {
          setError(err instanceof Error ? err.message : "Something went wrong.");
        }
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, role, tick, ...deps]);

  return { data, loading, error, forbidden, refetch };
}
