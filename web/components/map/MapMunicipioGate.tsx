"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { CmMunicipioOption } from "@/lib/cm-portal-geo";
import { MAP_CM_MUNICIPIOS_API } from "@/lib/map-live-urls";

export type MapMunicipioSelection = { municipio: CmMunicipioOption; from: string; to: string };
const RECENT_KEY = "homes-map-recent-municipalities";
function norm(value: string) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/-/g, " ").trim();
}

export function MapMunicipioGate({ open, initialSlug, initialFrom, initialTo, onConfirm, onCancel }: {
  open: boolean;
  initialSlug?: string | null;
  initialFrom?: string;
  initialTo?: string;
  onConfirm: (selection: MapMunicipioSelection) => void;
  onCancel?: () => void;
}) {
  const [municipios, setMunicipios] = useState<CmMunicipioOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [q, setQ] = useState("");
  const [from, setFrom] = useState(initialFrom ?? "");
  const [to, setTo] = useState(initialTo ?? "");
  const [recent, setRecent] = useState<string[]>([]);
  const [active, setActive] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLFormElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    let cancelled = false;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    queueMicrotask(() => {
      if (cancelled) return;
      setQ(""); setActive(0); setFrom(initialFrom ?? ""); setTo(initialTo ?? "");
      try {
        const stored: unknown = JSON.parse(window.localStorage.getItem(RECENT_KEY) || "[]");
        setRecent(Array.isArray(stored) ? stored.filter((slug): slug is string => typeof slug === "string").slice(0, 4) : []);
      } catch { setRecent([]); }
    });
    return () => { cancelled = true; if (previousFocus?.isConnected) previousFocus.focus(); };
  }, [open, initialFrom, initialTo]);

  useEffect(() => {
    if (open && typeof window !== "undefined" && !window.matchMedia("(min-width: 768px)").matches) dialogRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (open && !loading && !loadErr && typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches) searchRef.current?.focus();
  }, [open, loading, loadErr]);

  useEffect(() => {
    if (!open || municipios.length > 0) return;
    const ac = new AbortController();
    void (async () => {
      await Promise.resolve();
      if (ac.signal.aborted) return;
      setLoading(true); setLoadErr(null);
      try {
        const load = async () => {
          const response = await fetch(MAP_CM_MUNICIPIOS_API, { signal: ac.signal });
          if (!response.ok) throw new Error("municipios");
          return await response.json() as { municipios?: CmMunicipioOption[] };
        };
        let body: { municipios?: CmMunicipioOption[] };
        try { body = await load(); } catch (error) {
          if (ac.signal.aborted) throw error;
          body = await load();
        }
        if (!ac.signal.aborted) setMunicipios((body.municipios ?? []).slice().sort((a, b) => b.n - a.n || a.nombre.localeCompare(b.nombre, "es")));
      } catch {
        if (!ac.signal.aborted) setLoadErr("No hemos podido cargar los municipios.");
      } finally { if (!ac.signal.aborted) setLoading(false); }
    })();
    return () => ac.abort();
  }, [open, municipios.length, retry]);

  const matches = useMemo(() => {
    const query = norm(q);
    if (!query) {
      const priority = [...new Set([...(initialSlug ? [initialSlug] : []), ...recent])];
      const first = priority.flatMap(slug => municipios.find(m => m.slug === slug) ?? []);
      return [...first, ...municipios.filter(m => !priority.includes(m.slug))].slice(0, 12);
    }
    const words = query.split(/\s+/);
    const score = (m: CmMunicipioOption) => norm(m.nombre) === query || norm(m.slug) === query ? 0 : norm(m.nombre).startsWith(query) ? 1 : 2;
    return municipios.filter(m => words.every(word => `${norm(m.nombre)} ${norm(m.slug)}`.includes(word)))
      .sort((a, b) => score(a) - score(b) || b.n - a.n).slice(0, 12);
  }, [municipios, q, recent, initialSlug]);
  const datesOk = !from || !to || from <= to;
  const choose = (municipio: CmMunicipioOption) => {
    if (!datesOk) return;
    const next = [municipio.slug, ...recent.filter(slug => slug !== municipio.slug)].slice(0, 4);
    setRecent(next);
    try { if (typeof window !== "undefined") window.localStorage.setItem(RECENT_KEY, JSON.stringify(next)); } catch { /* Browsing remains available without storage. */ }
    onConfirm({ municipio, from, to });
  };
  if (!open) return null;

  return (
    <div className="absolute inset-0 z-[2400] flex items-end justify-center bg-[#142e2b]/40 p-2 backdrop-blur-sm sm:items-center sm:p-6">
      {onCancel ? <button type="button" aria-label="Volver al mapa" onClick={onCancel} className="absolute inset-0 cursor-default" tabIndex={-1} /> : null}
      <form ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} className="relative flex max-h-[min(100%,760px)] w-full max-w-[620px] flex-col overflow-hidden rounded-3xl border border-white/80 bg-[#fafbf8] shadow-[0_24px_90px_rgba(20,46,43,.28)]"
        onSubmit={e => { e.preventDefault(); if (matches[active]) choose(matches[active]); }}
        onKeyDown={e => {
          if (e.key === "Escape" && onCancel) { e.preventDefault(); onCancel(); }
          if (e.key === "Tab") {
            const elements = [...(dialogRef.current?.querySelectorAll<HTMLElement>('input:not(:disabled),button:not(:disabled):not([tabindex="-1"]),summary') ?? [])].filter(element => element.getClientRects().length);
            const first = elements[0], last = elements.at(-1);
            if (e.shiftKey && document.activeElement === first && last) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last && first) { e.preventDefault(); first.focus(); }
          }
        }}>
        <header className="map-municipality-heading relative shrink-0 overflow-hidden border-b border-[#dce6df] bg-gradient-to-br from-[#e3ede4] to-[#f6f5ed] px-5 pb-5 pt-6 sm:px-7 sm:pt-7">
          <svg className="pointer-events-none absolute -right-12 -top-8 h-48 w-72 opacity-20" viewBox="0 0 280 180" fill="none" aria-hidden="true"><path d="m5 90 65-40 90 35 100-60M70 50l10 85 80-50 25 75M10 150l70-15 105 25 90-70" stroke="#4a7578" strokeWidth="2" /><path d="m115 25 44 15-14 25-43-13zm70 73 40 13-10 25-43-11z" fill="#4a7578" /></svg>
          <div className="relative flex items-start justify-between gap-3"><div><p className="mb-2 text-[10px] font-bold uppercase tracking-[.18em] text-[#4a7578]">Explora el territorio</p><h2 id={`${id}-title`} className="text-2xl font-bold tracking-tight text-[#253c38] sm:text-[28px]">¿Qué quieres ver?</h2><p className="mt-2 text-sm text-[#516663]">Elige un municipio y entra directamente en su mapa.</p></div>{onCancel ? <button type="button" onClick={onCancel} aria-label="Cerrar selector" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/80 text-xl text-[#516663] hover:bg-white">×</button> : null}</div>
          <label className="relative mt-5 block"><span className="sr-only">Buscar municipio</span><svg className="pointer-events-none absolute left-3.5 top-3.5 text-[#4a7578]" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.7" /><path d="m16 16 4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg><input ref={searchRef} type="search" role="combobox" aria-controls={`${id}-results`} aria-expanded={matches.length > 0} aria-autocomplete="list" aria-activedescendant={matches[active] ? `${id}-${matches[active].slug}` : undefined}
            value={q} onChange={e => { setQ(e.target.value); setActive(0); }}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); if (matches[active]) choose(matches[active]); } if ((e.key === "ArrowDown" || e.key === "ArrowUp") && matches.length) { e.preventDefault(); const next = (active + (e.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length; setActive(next); if (typeof document !== "undefined") document.getElementById(`${id}-${matches[next].slug}`)?.scrollIntoView({ block: "nearest" }); } }}
            placeholder={loading ? "Cargando municipios…" : "Escribe un municipio…"} disabled={loading || Boolean(loadErr)} autoComplete="off" spellCheck={false}
            className="w-full rounded-xl border border-white bg-white py-3 pl-11 pr-4 text-base text-slate-800 shadow-sm outline-none placeholder:text-slate-400 focus:border-[#4a7578] focus:ring-2 focus:ring-[#4a7578]/15" /></label>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4 sm:px-7">
          {loadErr ? <div role="alert" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800"><p>{loadErr}</p><button type="button" className="mt-2 rounded-lg border border-amber-200 bg-white px-3 py-2 font-semibold" onClick={() => setRetry(n => n + 1)}>Reintentar</button></div> : null}
          <div className="mb-3 flex items-center justify-between gap-2"><h3 className="text-xs font-semibold text-slate-600">{q.trim() ? "Resultados de búsqueda" : recent.length || initialSlug ? "Tus municipios y más lugares" : "Municipios con más proyectos"}</h3>{municipios.length ? <span className="text-[10px] text-slate-400">{municipios.length.toLocaleString("es-ES")} disponibles</span> : null}</div>
          {loading ? <div role="status" className="grid grid-cols-2 gap-2.5">{Array.from({length: 6}, (_, index) => <div key={index} className="h-20 animate-pulse rounded-xl bg-slate-100" />)}<span className="sr-only">Cargando municipios</span></div> : null}
          <ul id={`${id}-results`} role="listbox" aria-label="Municipios disponibles" className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {matches.map((m, index) => <li key={m.slug} role="presentation"><button id={`${id}-${m.slug}`} type="button" role="option" aria-selected={active === index} disabled={!datesOk} onClick={() => choose(m)} onFocus={() => setActive(index)}
              className={`group flex min-h-[74px] w-full items-center justify-between gap-3 rounded-xl border bg-white px-3.5 py-3 text-left transition hover:-translate-y-0.5 hover:border-[#4a7578] hover:shadow-md focus-visible:outline-2 focus-visible:outline-[#4a7578] disabled:opacity-50 ${active === index ? "border-[#b6cac3] bg-[#f2f7f2]" : "border-[#e2e8e1]"}`}>
              <span className="min-w-0"><span className="block truncate text-sm font-bold text-[#253c38]">{m.nombre}</span><span className="mt-1 block text-[11px] text-slate-500">{m.n.toLocaleString("es-ES")} proyectos{m.slug === initialSlug ? " · En el mapa" : recent.includes(m.slug) ? " · Reciente" : ""}</span></span><svg className="shrink-0 text-[#4a7578] transition group-hover:translate-x-0.5" width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button></li>)}
          </ul>
          {!loading && !loadErr && !matches.length ? <div className="py-8 text-center"><p className="text-sm font-medium text-slate-700">No encontramos ese municipio.</p><p className="mt-1 text-xs text-slate-500">Prueba con otra parte del nombre.</p></div> : null}
          <details className="mt-4 rounded-xl border border-[#e2e8e1] bg-white px-3.5 py-3" open={from || to ? true : undefined}>
            <summary className="cursor-pointer text-xs font-semibold text-[#516663]">Filtrar por última actividad <span className="font-normal text-slate-400">· {from || to ? "Filtro activo" : "Opcional"}</span></summary>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">Puedes elegir fechas ahora o ajustarlas después desde el panel del mapa.</p><div className="mt-3 grid grid-cols-2 gap-3">{[{label: "Desde", value: from, set: setFrom}, {label: "Hasta", value: to, set: setTo}].map(field => <label key={field.label} className="block text-xs text-slate-600">{field.label}<input type="date" value={field.value} onChange={e => field.set(e.target.value)} className="mt-1 w-full min-w-0 rounded-lg border border-slate-200 p-2 outline-none focus:border-[#4a7578]" /></label>)}</div>
            {from || to ? <button type="button" onClick={() => { setFrom(""); setTo(""); }} className="mt-3 text-xs font-semibold text-[#1f4f53] hover:underline">Quitar fechas</button> : null}
            {!datesOk ? <p role="alert" className="mt-2 text-xs text-amber-800">La fecha inicial debe ser anterior a la final.</p> : null}
          </details>
        </div>
        <footer className="flex shrink-0 items-center justify-between gap-3 border-t border-[#e2e8e1] px-5 py-3 text-[10px] text-slate-400 sm:px-7"><span>Pulsa un municipio para explorar</span><span className="hidden sm:inline">↑ ↓ para elegir · Enter para entrar</span></footer>
      </form>
    </div>
  );
}
