/** First-party session measurement. Never starts before explicit consent. */
export const CONSENT_KEY = "homes_analytics_consent_v1";
const SESSION_KEY = "homes_analytics_session_v1";
const IDLE_MS = 30 * 60 * 1000;
const CONSENT_MS = 180 * 24 * 60 * 60 * 1000;
export type Consent = "accepted" | "rejected" | null;
export type AnalyticsProps = Record<string, string | number | boolean | null>;
type Session = { id: string; lastActivity: number; source: string };
type MeasurementEvent = { id: string; session: string; page: string; name: string; path: string; source: string; at: number; props: AnalyticsProps };
let session: Session | null = null;
let page = "";
let path = "";
let queue: MeasurementEvent[] = [];
let busy = false;

export function analyticsEnabled() {
  return process.env.NEXT_PUBLIC_SESSION_ANALYTICS === "1";
}

export function readConsent(): Consent {
  if (typeof window === "undefined") return null;
  try {
    const saved = JSON.parse(localStorage.getItem(CONSENT_KEY) || "null");
    return saved && Date.now() - saved.at < CONSENT_MS && ["accepted", "rejected"].includes(saved.value) ? saved.value : null;
  } catch { return null; }
}

export function writeConsent(value: Exclude<Consent, null>) {
  try { localStorage.setItem(CONSENT_KEY, JSON.stringify({ value, at: Date.now() })); } catch { /* Storage unavailable: stay opted out. */ }
  if (value === "rejected") {
    queue = []; session = null; page = ""; path = "";
    try { sessionStorage.removeItem(SESSION_KEY); } catch { /* No storage. */ }
  }
  window.dispatchEvent(new Event("homes-analytics-consent"));
}

function entrySource() {
  try {
    const host = new URL(document.referrer).hostname.replace(/^www\./, "");
    if (host === location.hostname.replace(/^www\./, "")) return "internal";
    if (/^google\.[a-z.]+$/.test(host)) return "google";
    if (host === "bing.com") return "bing";
    return "other";
  } catch { return "direct"; }
}

function getSession() {
  if (!session) {
    try { session = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null"); } catch { session = null; }
  }
  if (!session || typeof session.id !== "string" || !/^[a-f0-9-]{36}$/.test(session.id) || typeof session.lastActivity !== "number" || Date.now() - session.lastActivity >= IDLE_MS) {
    const previous = session;
    session = { id: crypto.randomUUID(), lastActivity: Date.now(), source: previous ? "internal" : entrySource() };
    page = "";
    if (previous) window.dispatchEvent(new Event("homes-analytics-session"));
  }
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(session)); } catch { /* Memory-only session. */ }
  return session;
}

export function touchAnalyticsSession() {
  if (!measurementAllowed()) return;
  const current = getSession();
  current.lastActivity = Date.now();
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(current)); } catch { /* Memory-only session. */ }
}

export function measurementAllowed() {
  return typeof window !== "undefined" && analyticsEnabled() && readConsent() === "accepted" && !location.pathname.startsWith("/admin") && !navigator.webdriver;
}

/** Route IDs are useful for projects; addresses, query strings and fragments are not collected. */
export function safeAnalyticsPath(value: string) {
  const clean = value.split(/[?#]/)[0];
  if (clean.startsWith("/ubicacion")) return "/ubicacion";
  if (!/^\/[a-zA-Z0-9/%:_-]*$/.test(clean) || clean.length > 240) return "/otra";
  return clean;
}

export function startAnalyticsPage() {
  if (!measurementAllowed()) return;
  getSession();
  if (page && path === safeAnalyticsPath(location.pathname)) return page;
  path = safeAnalyticsPath(location.pathname);
  page = crypto.randomUUID();
  recordSessionEvent("page_view");
  return page;
}

export function recordPageEngagement(pageId: string | undefined, props: AnalyticsProps) {
  if (pageId && pageId === page) recordSessionEvent("page_engagement", props);
}

export function recordSessionEvent(name: string, props: AnalyticsProps = {}) {
  if (!measurementAllowed()) return;
  if (name === "page_engagement" && session && Date.now() - session.lastActivity >= IDLE_MS) return;
  const current = getSession();
  if (!page || (name !== "page_engagement" && path !== safeAnalyticsPath(location.pathname))) {
    path = safeAnalyticsPath(location.pathname); page = crypto.randomUUID();
    if (name !== "page_view") queue.push({ id: crypto.randomUUID(), session: current.id, page, path, source: current.source, name: "page_view", at: Date.now(), props: {} });
  }
  if (name !== "page_engagement") touchAnalyticsSession();
  queue.push({ id: crypto.randomUUID(), session: current.id, page, path, source: current.source, name, at: Date.now(), props });
  queue = queue.slice(-40);
}

export async function flushAnalytics(beacon = false) {
  if (!measurementAllowed() || !queue.length || busy) return;
  const batch = queue.splice(0, 20);
  const body = JSON.stringify({ consent: true, events: batch });
  if (beacon && navigator.sendBeacon("/api/analytics", new Blob([body], { type: "application/json" }))) return;
  busy = true;
  try {
    const response = await fetch("/api/analytics", { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true });
    if (response.status >= 500 && measurementAllowed()) queue = [...batch, ...queue].slice(-40);
  } catch { if (measurementAllowed()) queue = [...batch, ...queue].slice(-40); }
  finally { busy = false; }
}
