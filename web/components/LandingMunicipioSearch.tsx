"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { CmMunicipioOption } from "@/lib/cm-portal-geo";
import { MAP_CM_MUNICIPIOS_API } from "@/lib/map-live-urls";

const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/-/g, " ").trim();

export function LandingMunicipioSearch() {
  const router = useRouter();
  const id = useId();
  const [municipios, setMunicipios] = useState<CmMunicipioOption[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [status, setStatus] = useState("loading");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetch(MAP_CM_MUNICIPIOS_API, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(); return response.json(); })
      .then(data => { setMunicipios(data.municipios ?? []); setStatus("ready"); })
      .catch(() => { if (!controller.signal.aborted) setStatus("error"); });
    return () => controller.abort();
  }, [retry]);
  const matches = useMemo(() => {
    const q = normalize(query);
    return municipios.filter(m => q.split(/\s+/).every(word => normalize(`${m.nombre} ${m.slug}`).includes(word)))
      .sort((a, b) => Number(normalize(b.nombre).startsWith(q)) - Number(normalize(a.nombre).startsWith(q)) || b.n - a.n).slice(0, 5);
  }, [municipios, query]);
  const choose = (municipio: CmMunicipioOption) => router.push(`/explore?municipio=${encodeURIComponent(municipio.slug)}`);
  return (
    <div className="landing-municipio-search" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
      <form onSubmit={event => { event.preventDefault(); if (matches[active]) choose(matches[active]); }} className="landing-search-field">
        <svg width="23" height="23" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.5"/><path d="m16 16 4.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        <input aria-label="Buscar municipio" role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={`${id}-results`} aria-activedescendant={open && matches[active] ? `${id}-${active}` : undefined} placeholder="Busca un municipio" autoComplete="off" spellCheck={false} value={query}
          onFocus={() => setOpen(true)} onChange={event => { setQuery(event.target.value); setActive(0); setOpen(true); }}
          onKeyDown={event => {
            if (event.key === "Escape") setOpen(false);
            if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); setOpen(true); setActive(index => (index + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % (matches.length || 1)); }
          }}/>
        <button type="submit" aria-label="Explorar municipio" disabled={!matches.length}>↗</button>
      </form>
      {open && <div className="landing-search-results">
        <p className="px-5 pb-2 pt-4 text-xs text-slate-500">{query ? "Municipios" : "Explora un municipio"}</p>
        <ul id={`${id}-results`} role="listbox" aria-label="Municipios">
          {matches.map((m, index) => <li key={m.slug} role="option" id={`${id}-${index}`} aria-selected={index === active}>
            <button type="button" onClick={() => choose(m)} onMouseEnter={() => setActive(index)} className={`flex w-full items-center justify-between px-5 py-3 text-left ${index === active ? "bg-[#edf2ed]" : "hover:bg-[#f5f6f2]"}`}><span className="font-medium">{m.nombre}</span><span className="text-xs text-slate-500">{m.n.toLocaleString("es-ES")} proyectos <span className="ml-3">↗</span></span></button>
          </li>)}
        </ul>
        <div role="status" className="px-5 py-3 text-xs text-slate-500">
          {status === "loading" ? "Cargando municipios…" : status === "error" ? <><span>No se han podido cargar los municipios. </span><button type="button" className="underline" onClick={() => { setStatus("loading"); setRetry(n => n + 1); }}>Reintentar</button></> : !matches.length ? "No encontramos ese municipio. Prueba con otro nombre." : `${municipios.length.toLocaleString("es-ES")} municipios disponibles`}
        </div>
      </div>}
      <p className="mt-5 text-sm text-[var(--portal-ink)]/60">Selecciona un municipio para acceder a sus proyectos.</p>
    </div>
  );
}
