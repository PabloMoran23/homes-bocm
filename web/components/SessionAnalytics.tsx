"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { flushAnalytics, measurementAllowed, recordPageEngagement, recordSessionEvent, startAnalyticsPage, touchAnalyticsSession } from "@/lib/session-analytics";

export function SessionAnalytics() {
  const pathname = usePathname();
  const [sessionVersion, setSessionVersion] = useState(0);

  useEffect(() => {
    const renew = () => setSessionVersion(v => v + 1);
    window.addEventListener("homes-analytics-session", renew);
    return () => window.removeEventListener("homes-analytics-session", renew);
  }, []);

  useEffect(() => {
    if (!measurementAllowed()) return;
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
  }, [pathname, sessionVersion]);

  return null;
}
