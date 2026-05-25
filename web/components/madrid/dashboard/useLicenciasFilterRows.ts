"use client";

import { useEffect, useState } from "react";
import type { LicenciasFilterRowsFile } from "@/lib/licencias-dashboard-filters";

const FILTER_ROWS_URL = "/data/madrid-licencias-filter-rows.json";

export function useLicenciasFilterRows() {
  const [data, setData] = useState<LicenciasFilterRowsFile | null>(null);
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
        if (!cancelled) setData(json as LicenciasFilterRowsFile);
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
