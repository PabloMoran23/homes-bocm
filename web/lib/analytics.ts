import { track } from "@vercel/analytics";

type AnalyticsProps = Record<string, string | number | boolean | null>;

/** Evento custom en Vercel Web Analytics. No-op fuera del cliente. */
export function trackEvent(name: string, props?: AnalyticsProps): void {
  if (typeof window === "undefined") return;
  track(name, props);
}
