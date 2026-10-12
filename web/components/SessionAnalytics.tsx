"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { analyticsEnabled, flushAnalytics, measurementAllowed, readConsent, recordPageEngagement, recordSessionEvent, startAnalyticsPage, touchAnalyticsSession, writeConsent, type Consent } from "@/lib/session-analytics";

export function SessionAnalytics() {
  const pathname = usePathname();
  const [consent, setConsent] = useState<Consent>(null);
  const [ready, setReady] = useState(false);
  const [settings, setSettings] = useState(false);
  const [details, setDetails] = useState(false);
  const [sessionVersion, setSessionVersion] = useState(0);
  const publicPage = !pathname.startsWith("/admin");

  useEffect(() => {
    const sync = () => { setConsent(readConsent()); setReady(true); };
    const renew = () => setSessionVersion(v => v + 1);
    sync();
    window.addEventListener("homes-analytics-consent", sync);
    window.addEventListener("storage", sync);
    window.addEventListener("homes-analytics-session", renew);
    return () => { window.removeEventListener("homes-analytics-consent", sync); window.removeEventListener("storage", sync); window.removeEventListener("homes-analytics-session", renew); };
  }, []);

  useEffect(() => {
    if (consent !== "accepted" || !publicPage || !measurementAllowed()) return;
    const pageId = startAnalyticsPage();
    let activeMs = 0;
    let maxScroll = 0;
    let lastTick = Date.now();
    let lastActivity = Date.now();
    const activity = () => { lastActivity = Date.now(); touchAnalyticsSession(); };
    const sample = () => {
      const now = Date.now();
      if (document.visibilityState === "visible" && now - lastActivity < 60_000) activeMs += Math.min(now - lastTick, 5_000);
      lastTick = now;
    };
    const scroll = () => {
      activity();
      const height = document.documentElement.scrollHeight - innerHeight;
      if (height > 0) maxScroll = Math.max(maxScroll, Math.min(100, Math.round(scrollY / height * 100)));
    };
    const engagement = () => { sample(); recordPageEngagement(pageId, { active_seconds: Math.round(activeMs / 1000), scroll_percent: maxScroll }); };
    const click = (event: MouseEvent) => {
      activity();
      const anchor = event.target instanceof Element ? event.target.closest("a") : null;
      if (!(anchor instanceof HTMLAnchorElement)) return;
      const url = new URL(anchor.href, location.origin);
      if (!["http:", "https:"].includes(url.protocol)) return;
      const external = url.origin !== location.origin;
      const documentLink = anchor.hasAttribute("download") || /\.(pdf|docx?|xlsx?|zip)(?:$|\/)/i.test(url.pathname) || url.pathname.startsWith("/api/nti") || /document|bolet[ií]n|pdf/i.test(anchor.textContent || "");
      if (documentLink || external) {
        recordSessionEvent(documentLink ? "document_click" : "outbound_click", { destination_host: url.hostname, document_type: /\.pdf$/i.test(url.pathname) ? "pdf" : "other" });
        void flushAnalytics(true);
      }
    };
    const hide = () => { engagement(); void flushAnalytics(true); };
    const visibility = () => { if (document.visibilityState === "hidden") hide(); else lastTick = Date.now(); };
    const interval = window.setInterval(() => { engagement(); void flushAnalytics(); }, 15_000);
    const tick = window.setInterval(sample, 1_000);
    document.addEventListener("click", click);
    document.addEventListener("scroll", scroll, { passive: true });
    document.addEventListener("pointerdown", activity, { passive: true });
    document.addEventListener("keydown", activity);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", hide);
    void flushAnalytics();
    return () => {
      engagement(); void flushAnalytics(true);
      clearInterval(interval); clearInterval(tick);
      document.removeEventListener("click", click); document.removeEventListener("scroll", scroll);
      document.removeEventListener("pointerdown", activity); document.removeEventListener("keydown", activity);
      document.removeEventListener("visibilitychange", visibility); window.removeEventListener("pagehide", hide);
    };
  }, [pathname, consent, publicPage, sessionVersion]);

  if (!analyticsEnabled() || !ready || !publicPage) return null;
  if (consent !== null && !settings) return <button type="button" onClick={() => setSettings(true)} className="fixed bottom-2 left-2 z-[1200] rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 shadow-sm">Privacidad</button>;
  const choose = (value: "accepted" | "rejected") => { writeConsent(value); setSettings(false); };
  return (
    <section aria-label="Preferencias de analítica" className="fixed bottom-3 left-3 right-3 z-[1200] mx-auto max-w-xl rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-xl">
      <p className="font-semibold text-slate-900">Ayúdanos a mejorar Homes</p>
      <p className="mt-1">Si aceptas, mediremos las páginas que consultas, el tiempo de actividad y los clics para entender qué información resulta útil. Puedes usar toda la web si rechazas.</p>
      <button type="button" className="mt-2 underline" aria-expanded={details} onClick={() => setDetails(!details)}>Qué datos guardamos</button>
      {details && <p className="mt-2 text-xs leading-relaxed">Guardamos un identificador aleatorio de sesión por pestaña, el origen de entrada (como Google), las páginas, zonas generales, filtros, resultados y clics. No guardamos IP, direcciones completas, búsquedas escritas ni grabaciones. La sesión caduca tras 30 minutos sin actividad. Los eventos se eliminan después de 90 días y tu elección se recuerda durante 180 días. Puedes retirar el permiso desde «Privacidad».</p>}
      <div className="mt-3 flex gap-3">
        <button type="button" onClick={() => choose("rejected")} className="flex-1 rounded-lg border border-slate-300 px-4 py-2 font-medium">Rechazar analítica</button>
        <button type="button" onClick={() => choose("accepted")} className="flex-1 rounded-lg border border-slate-300 px-4 py-2 font-medium">Aceptar analítica</button>
      </div>
    </section>
  );
}
