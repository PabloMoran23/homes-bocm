import { track } from "@vercel/analytics";
import { measurementAllowed, recordSessionEvent } from "@/lib/session-analytics";

type AnalyticsProps = Record<string, string | number | boolean | null>;

/** Events for the first-party session and Vercel. No-op on server. */
export function trackEvent(name: string, props?: AnalyticsProps): void {
  if (typeof window === "undefined") return;
  recordSessionEvent(name, props);
  if (measurementAllowed()) {
    try { track(name, props); } catch { /* Analytics must never break the product. */ }
  }
}
