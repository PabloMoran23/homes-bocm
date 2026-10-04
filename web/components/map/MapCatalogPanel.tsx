"use client";

import { useRef, useState, type ReactNode } from "react";
import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";
import type { MapProjectSpotlightItem } from "@/lib/map-project-spotlight";
import type { CmPortalMapMeta } from "@/lib/cm-portal-geo";

export function MapCatalogPanel({ open, onOpen, onClose, municipality, onChangeMunicipality, items, selectedId, onSelect, query, onQuery, category, onCategory, categories, totalLoaded, meta, loading, error, showProjects, onToggleProjects, showLicenses, onToggleLicenses, from, to, onFrom, onTo, others, licenseControls, showLayerControls = true }: {
  open: boolean; onOpen: () => void; onClose: () => void; municipality: string; onChangeMunicipality: () => void;
  items: MapProjectSpotlightItem[]; selectedId?: string; onSelect: (id: string) => void;
  query: string; onQuery: (value: string) => void; category: string; onCategory: (value: string) => void; categories: string[];
  totalLoaded: number; meta: CmPortalMapMeta | null; loading: boolean; error: string | null;
  showProjects: boolean; onToggleProjects: () => void; showLicenses: boolean; onToggleLicenses: () => void;
  from: string; to: string; onFrom: (value: string) => void; onTo: (value: string) => void;
  showLayerControls?: boolean;
  others: MapProjectSpotlightItem[]; licenseControls?: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const dragStart = useRef(0);
  const dragged = useRef(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const active = Boolean(from || to || category);
  const button = "min-h-11 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold hover:bg-slate-50";
  const collapsedButton = <button type="button" onClick={onOpen} className={`absolute left-3 max-w-[calc(100%-5rem)] z-[1200] rounded-xl border border-white bg-white px-4 py-3 text-sm font-semibold text-[#1f4f53] shadow-lg lg:bottom-auto lg:top-4 ${selectedId ? "top-3" : "bottom-3"}`}>{municipality} · Proyectos y filtros</button>;
  if (!open) return collapsedButton;
  return <>{selectedId ? <div className="lg:hidden">{collapsedButton}</div> : null}<aside aria-label="Catálogo y controles del mapa" className={`map-catalog-panel ${selectedId ? "hidden lg:flex" : "flex"} absolute inset-x-0 bottom-0 z-[1200] ${expanded ? "h-[70%]" : "h-[25%]"} max-h-[70%] flex-col overflow-hidden rounded-t-2xl border border-[#e4e8e3] bg-[#fafbf8] shadow-xl lg:inset-x-auto lg:bottom-0 lg:left-0 lg:top-0 lg:h-auto lg:max-h-none lg:w-[350px] lg:rounded-none lg:shadow-none`}>
    <button type="button" aria-label={expanded ? "Reducir panel" : "Ampliar panel"} aria-expanded={expanded}
      className="flex min-h-11 shrink-0 touch-none flex-col items-center justify-center gap-1 text-[10px] font-semibold text-[#4a7578] lg:hidden"
      onPointerDown={e => { dragStart.current = e.clientY; dragged.current = false; e.currentTarget.setPointerCapture(e.pointerId); }}
      onPointerUp={e => { const delta = dragStart.current - e.clientY; if (Math.abs(delta) > 32) { dragged.current = true; setExpanded(delta > 0); } }}
      onClick={() => { if (dragged.current) { dragged.current = false; return; } setExpanded(v => !v); }}>
      <span className="h-1 w-10 rounded-full bg-slate-300" />
    </button>
    {!expanded ? <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-200 px-4 pb-2 lg:hidden"><div className="min-w-0"><h2 className="truncate text-base font-bold text-slate-800">{municipality}</h2><p className="text-[11px] text-slate-500">Explorar proyectos · {items.length} en esta zona</p></div><button type="button" onClick={onChangeMunicipality} className="min-h-11 shrink-0 rounded-lg border border-[#b6cac3] bg-white px-2 text-[11px] font-semibold text-[#1f4f53]">Cambiar municipio</button></div> : null}
    <header className={`${expanded ? "flex" : "hidden lg:flex"} shrink-0 items-start justify-between gap-2 border-b border-slate-200 px-4 py-4`}>
      <div className="min-w-0"><p className="mb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[#4a7578]">Explorar proyectos</p><h2 className="break-words text-xl font-bold text-slate-800">{municipality}</h2><p className="mt-1 text-xs text-slate-500">{(meta?.proyectosEnRango ?? 0).toLocaleString("es-ES")} proyectos{from || to ? " en el periodo" : " en el municipio"}</p><button type="button" onClick={onChangeMunicipality} className="mt-3 rounded-lg border border-[#b6cac3] bg-white px-3 py-2 text-xs font-semibold text-[#1f4f53] shadow-sm transition hover:bg-[#e4eee7] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#4a7578]">Cambiar municipio</button></div>
      <button type="button" aria-label="Plegar panel" onClick={onClose} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-xl text-slate-500 hover:bg-slate-100">×</button>
    </header>
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className={`${expanded ? "block" : "hidden lg:block"} space-y-3 border-b border-slate-200 p-4`}>
        <label className="block"><span className="sr-only">Buscar en esta zona por nombre o expediente</span><input value={query} onChange={e => onQuery(e.target.value)} placeholder="Buscar en esta zona…" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-base outline-none lg:text-sm focus:border-[#4a7578]" /></label>
        <div className="flex items-center justify-between"><button type="button" className={button} aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}>Filtros{active ? " · activos" : ""}</button>{query || active ? <button type="button" className="text-xs text-[#1f4f53] hover:underline" onClick={() => { onQuery(""); onCategory(""); onFrom(""); onTo(""); }}>Limpiar</button> : null}</div>
        {filtersOpen ? <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3"><label className="block text-xs text-slate-600">Categoría<select value={category} onChange={e => onCategory(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-base lg:text-xs"><option value="">Todas las categorías</option>{categories.map(c => <option key={c} value={c}>{c}</option>)}</select></label><fieldset><legend className="mb-1 text-xs text-slate-600">Última actividad</legend><div className="grid grid-cols-2 gap-2"><label className="text-xs text-slate-500">Desde<input type="date" value={from} onChange={e => onFrom(e.target.value)} className="mt-1 w-full min-w-0 rounded-lg border border-slate-200 p-2 text-base lg:text-xs" /></label><label className="text-xs text-slate-500">Hasta<input type="date" value={to} onChange={e => onTo(e.target.value)} className="mt-1 w-full min-w-0 rounded-lg border border-slate-200 p-2 text-base lg:text-xs" /></label></div>{from && to && from > to ? <p className="mt-2 text-xs text-amber-800">La fecha inicial debe ser anterior a la final.</p> : null}</fieldset><p className="text-[11px] leading-relaxed text-slate-500">Categorías y búsqueda filtran los proyectos cargados. Las fechas se aplican al municipio.</p></div> : null}
        {category ? <button type="button" onClick={() => onCategory("")} className="rounded-full bg-[#e4eee7] px-3 py-1 text-xs text-[#1f4f53]">{category} ×</button> : null}
        {showLayerControls ? <div><p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">Capas del mapa</p><div className="grid grid-cols-2 gap-2">{[{label:"Proyectos",on:showProjects,toggle:onToggleProjects},{label:"Licencias",on:showLicenses,toggle:onToggleLicenses}].map(layer => <button type="button" key={layer.label} aria-pressed={layer.on} onClick={layer.toggle} className={`${button} ${layer.on ? "border-[#4a7578] bg-[#e4eee7] text-[#1f4f53]" : "bg-white text-slate-500"}`}>{layer.on ? "✓ " : ""}{layer.label}</button>)}</div></div> : null}
        {showLayerControls && showLicenses && licenseControls ? <details><summary className="cursor-pointer text-xs font-semibold text-[#1f4f53]">Opciones de licencias</summary><div className="pt-2">{licenseControls}</div></details> : null}
      </div>
      {items.some(item => item.approx) ? <p className={`${expanded ? "block" : "hidden lg:block"} mx-4 mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800`}>Los marcadores con ubicación aproximada se reparten alrededor del centro. No indican una parcela exacta.</p> : null}
      <section className="p-3" aria-label="Proyectos de esta zona"><div className="mb-3 px-1"><div className="flex items-center justify-between"><h3 className="text-xs font-bold uppercase tracking-wide text-slate-700">Proyectos en esta zona</h3><span className="rounded-full bg-[#e4eee7] px-2 py-0.5 text-xs font-bold text-[#1f4f53]">{items.length}</span></div><p className="mt-1 text-[11px] text-slate-500">{totalLoaded} cargados · Mueve el mapa para explorar</p></div>
        <p aria-live="polite" className="text-xs text-slate-500">{loading ? "Actualizando esta zona…" : error || ""}</p>
        {!showProjects ? <p className="mb-2 rounded-lg bg-slate-100 p-2 text-xs text-slate-600">La capa de proyectos está oculta.</p> : null}
        <ul className="space-y-2">{items.map(item => <li key={item.id}><button type="button" aria-pressed={selectedId === item.id} onClick={() => onSelect(item.id)} className={`w-full rounded-xl border bg-white p-3 text-left transition hover:border-[#4a7578] ${selectedId === item.id ? "border-[#4a7578] ring-1 ring-[#4a7578]" : "border-slate-200"}`}><div className="flex items-start gap-2.5"><SigmaClassificationIcon clasificacion={item} size="sm" /><div className="min-w-0"><p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-[#4a7578]">{item.fase || item.categoryLabel}</p><h4 className="line-clamp-2 text-sm font-bold leading-snug text-slate-800">{item.title}</h4>{item.approx ? <span className="mt-1 inline-block rounded-full bg-amber-50 px-2 py-0.5 text-[9px] font-medium text-amber-800">Ubicación aproximada</span> : null}</div></div>{item.resumen ? <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500">{item.resumen}</p> : null}<div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-slate-500">{item.dateLabel ? <span>{item.dateLabel}</span> : null}{item.supM2 ? <span>{item.supM2.toLocaleString("es-ES")} m²</span> : null}{item.numViviendas ? <span>{item.numViviendas.toLocaleString("es-ES")} viviendas</span> : null}</div></button></li>)}</ul>
        {!items.length && !loading ? <p className="py-6 text-center text-xs text-slate-500">No hay proyectos para estos filtros en esta zona.</p> : null}
      </section>
      {others.length > 0 ? <details className="mx-3 mb-4 rounded-xl border border-slate-200 bg-white p-3"><summary className="cursor-pointer text-xs font-semibold text-slate-700">Otros proyectos · {(meta?.proyectosAproxTotal ?? others.length).toLocaleString("es-ES")}</summary><p className="my-2 text-[11px] leading-relaxed text-slate-500">Sin ubicación exacta o con ámbitos demasiado extensos. Mostramos {others.length}.</p><ul>{others.map(item => <li key={item.id}><a className="block border-t border-slate-100 py-2 text-xs font-medium text-[#1f4f53] hover:underline" href={item.href}>{item.title}</a></li>)}</ul></details> : null}
    </div>
  </aside></>;
}
