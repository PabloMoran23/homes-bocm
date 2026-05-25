"use client";

import { useEffect, useState } from "react";
import type { SigmaFilterRowsFile } from "@/lib/sigma-dashboard-filters";

const FILTER_ROWS_URL = "/data/madrid-sigma-filter-rows.json";

export function useSigmaFilterRows() {
  const [data, setData] = useState<SigmaFilterRowsFile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(FILTER_ROWS_URL)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((json) => {
        if (!cancelled) setData(json as SigmaFilterRowsFile);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading, error };
}
