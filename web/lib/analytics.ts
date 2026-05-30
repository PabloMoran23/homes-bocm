type AnalyticsProps = Record<string, string | number | boolean>;

declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: AnalyticsProps }) => void;
    gtag?: (...args: unknown[]) => void;
  }
}

const PLAUSIBLE_DOMAIN = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

export function isAnalyticsEnabled(): boolean {
  return Boolean(PLAUSIBLE_DOMAIN || GA_MEASUREMENT_ID);
}

/** Evento custom (Plausible y/o GA4). No-op si analítica no configurada. */
export function trackEvent(name: string, props?: AnalyticsProps): void {
  if (typeof window === "undefined") return;

  if (PLAUSIBLE_DOMAIN && window.plausible) {
    window.plausible(name, props ? { props } : undefined);
  }

  if (GA_MEASUREMENT_ID && window.gtag) {
    window.gtag("event", name, props);
  }
}
