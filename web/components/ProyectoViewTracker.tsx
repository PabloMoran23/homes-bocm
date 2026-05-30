"use client";

import { useEffect } from "react";
import { trackEvent } from "@/lib/analytics";

export function ProyectoViewTracker({
  id,
  kind,
}: {
  id: string;
  kind: "sigma" | "bocm";
}) {
  useEffect(() => {
    trackEvent("ficha_proyecto_ver", { id, kind });
  }, [id, kind]);

  return null;
}
