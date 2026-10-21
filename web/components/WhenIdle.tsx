"use client";

import { useEffect, useState, type ReactNode } from "react";

/** Keep heavy client chunks out of the first seconds of main-thread work. */
export function WhenIdle({
  children,
  delayMs = 5000,
  fallback = null,
}: {
  children: ReactNode;
  delayMs?: number;
  fallback?: ReactNode;
}) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs]);
  return ready ? children : fallback;
}
