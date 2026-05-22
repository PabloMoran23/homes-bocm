"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { normSearch } from "@/lib/madrid";
import { sigmaPassesPortalLink } from "@/lib/madrid-sigma-filters";
import {
  mapDateRangeFromInputs,
  passesMapDateRange,
  sigmaFeatureActivityMs,
  ubicacionActivityMs,
} from "@/lib/map-date-filters";
import { loadSigmaMetricsBundle, type MadridSigmaMetricsFile } from "@/lib/sigma-metrics";
import { filterSigmaMapFeaturesByBBox, SIGMA_MAP_DEFAULT_MAX_BBOX_KM2 } from "@/lib/sigma-map-geometry";
import {
  filterPointFeaturesInView,
  filterPolygonFeaturesInView,
  type MapBounds,
} from "@/lib/map-viewport";
import type { SigmaBocmPopupLink, SectorFeatureCollection } from "@/lib/sector-geo";
import type { UbicacionSearchItem } from "@/lib/ubicacion";
import { ubicacionPath } from "@/lib/ubicacion";
import type { MadridSigmaDataset } from "@/lib/types";
import { LICENCIA_MAPA_CONFIG } from "@/lib/licencia-mapa-config";
import type { LicenciaMapaCategoria } from "@/lib/licencia-tipos";
import {
  allLicenciaTiposEnabled,
  LICENCIA_TIPOS_FILTRABLES,
  passesLicenciaTipoFilter,
} from "@/lib/map-licencia-filters";
import {
  filterUbicacionesMadridCapital,
  type UbicacionesMapGeoJson,
} from "@/lib/madrid-ubicaciones-map";
import { ambitosProyectosEnVista, PROYECTOS_URBANISTICOS } from "@/lib/ui-labels";

const MadridUnifiedMap = dynamic(
  () => import("./MadridUnifiedMap").then((m) => ({ default: m.MadridUnifiedMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center bg-slate-100 text-sm text-slate-500">
        Cargando mapa…
      </div>
    ),
  },
);

type SigmaMapMode = "ambitos" | "ip" | "ad" | "gestion" | "urbanizacion";

const SIGMA_LAYER_URL: Record<Exclude<SigmaMapMode, "ambitos" | "ip">, string> = {
  ad: "/data/madrid-sigma-ad.geojson",
  gestion: "/data/madrid-sigma-gestion.geojson",
  urbanizacion: "/data/madrid-sigma-urbanizacion.geojson",
};

const SIGMA_MAP_MODES: { id: SigmaMapMode; label: string }[] = [
  { id: "ambitos", label: "Todos en mapa" },
  { id: "ip", label: "Inf. pública" },
  { id: "ad", label: "En curso" },
  { id: "gestion", label: "Gestión" },
  { id: "urbanizacion", label: "Urbanización" },
];

function layerToggleClass(active: boolean) {
  return active
    ? "bg-[var(--portal-accent)] text-white shadow-sm"
    : "text-slate-600 hover:bg-slate-100";
}

function MapLayerToolbar({
  showSigma,
  onToggleSigma,
  showUbicaciones,
  onToggleUbicaciones,
  mapMode,
  onMapModeChange,
  layerLoading,
}: {
  showSigma: boolean;
  onToggleSigma: () => void;
  showUbicaciones: boolean;
  onToggleUbicaciones: () => void;
  mapMode: SigmaMapMode;
  onMapModeChange: (mode: SigmaMapMode) => void;
  layerLoading: boolean;
}) {
  return (
    <div
      className="pointer-events-none absolute left-1/2 top-3 z-[1100] flex w-[min(100%,36rem)] -translate-x-1/2 justify-center px-3 sm:top-4"
      role="toolbar"
      aria-label="Capas del mapa"
    >
      <div className="pointer-events-auto flex max-w-full flex-wrap items-center justify-center gap-1 rounded-xl border border-white/90 bg-white/95 p-1 shadow-lg backdrop-blur-md">
        <button
          type="button"
          aria-pressed={showSigma}
          onClick={onToggleSigma}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition sm:text-sm ${layerToggleClass(showSigma)}`}
        >
          {PROYECTOS_URBANISTICOS}
          {layerLoading && showSigma ? (
            <span className="ml-1 font-normal opacity-80">…</span>
          ) : null}
        </button>
        <button
          type="button"
          aria-pressed={showUbicaciones}
          onClick={onToggleUbicaciones}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition sm:text-sm ${layerToggleClass(showUbicaciones)}`}
        >
          Licencias
        </button>
        {showSigma ? (
          <>
            <span className="mx-0.5 hidden h-5 w-px bg-slate-200 sm:block" aria-hidden />
            <label className="sr-only" htmlFor="sigma-map-mode">
              Vista de proyectos
            </label>
            <select
              id="sigma-map-mode"
              value={mapMode}
              onChange={(e) => onMapModeChange(e.target.value as SigmaMapMode)}
              className="max-w-[11rem] rounded-lg border-0 bg-slate-50 py-1.5 pl-2 pr-7 text-xs font-medium text-slate-800 ring-1 ring-slate-200/90 focus:ring-2 focus:ring-[var(--portal-accent)]/30 sm:max-w-none sm:text-sm"
            >
              {SIGMA_MAP_MODES.map(({ id, label }) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </>
        ) : null}
      </div>
    </div>
  );
}

function norm(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function Div({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={className}>{children}</div>;
}

export function ExploreMadridApp() {
  const router = useRouter();
  const [ubicGeo, setUbicGeo] = useState<UbicacionesMapGeoJson | null>(null);
  const [searchIndex, setSearchIndex] = useState<UbicacionSearchItem[]>([]);
  const [sigmaData, setSigmaData] = useState<MadridSigmaDataset | null>(null);
  const [ambitosGeo, setAmbitosGeo] = useState<SectorFeatureCollection | null>(null);
  const [ipGeo, setIpGeo] = useState<SectorFeatureCollection | null>(null);
  const [geoCache, setGeoCache] = useState<Partial<Record<SigmaMapMode, SectorFeatureCollection>>>({});
  const [bocmByExp, setBocmByExp] = useState<Record<string, SigmaBocmPopupLink[]> | null>(null);
  const [metricsBundle, setMetricsBundle] = useState<MadridSigmaMetricsFile | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  /** En escritorio el panel lateral arranca abierto (solo al montar, sin forzar al redimensionar). */
  useEffect(() => {
    if (window.matchMedia("(min-width: 640px)").matches) {
      setPanelOpen(true);
    }
  }, []);

  const [q, setQ] = useState("");
  const [highlightNdp, setHighlightNdp] = useState<string | null>(null);
  const [openSuggest, setOpenSuggest] = useState(false);
  const [showUbicaciones, setShowUbicaciones] = useState(true);
  const [showSigma, setShowSigma] = useState(false);
  const [mapBounds, setMapBounds] = useState<MapBounds | null>(null);
  const [dataReady, setDataReady] = useState({ ubic: false, search: false });
  const [mapMode, setMapMode] = useState<SigmaMapMode>("ambitos");
  const [layerLoading, setLayerLoading] = useState(false);
  const [showHugeSigmaPolygons, setShowHugeSigmaPolygons] = useState(false);
  const [sigmaMapOnlyWithPortal, setSigmaMapOnlyWithPortal] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const dateRange = useMemo(
    () => mapDateRangeFromInputs(dateFrom, dateTo),
    [dateFrom, dateTo],
  );
  const dateFilterActive = Boolean(dateFrom || dateTo);
  const [licenciaTiposEnabled, setLicenciaTiposEnabled] = useState<Set<LicenciaMapaCategoria>>(
    () => allLicenciaTiposEnabled(),
  );
  const licenciaTipoFilterActive =
    licenciaTiposEnabled.size < LICENCIA_TIPOS_FILTRABLES.length;

  const toggleLicenciaTipo = useCallback((cat: LicenciaMapaCategoria) => {
    setLicenciaTiposEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mapRes, searchRes] = await Promise.all([
          fetch("/data/ubicaciones-map.geojson"),
          fetch("/data/ubicaciones-search.json"),
        ]);
        if (!mapRes.ok || !searchRes.ok) throw new Error("ubicaciones");
        if (!cancelled) {
          setUbicGeo((await mapRes.json()) as UbicacionesMapGeoJson);
          setSearchIndex((await searchRes.json()) as UbicacionSearchItem[]);
          setDataReady({ ubic: true, search: true });
        }
      } catch {
        if (!cancelled) {
          setErr(
            "Faltan datos de Madrid. Ejecuta: npm run build-data (y db/ingest_madrid_ubicacion.py si aplica).",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Carga SIGMA bajo demanda (evita ~25 MB + miles de polígonos al abrir). */
  useEffect(() => {
    if (!showSigma || ambitosGeo) return;
    let cancelled = false;
    setLayerLoading(true);
    (async () => {
      try {
        const [sigmaRes, ambitosRes] = await Promise.all([
          fetch("/data/madrid-sigma.json"),
          fetch("/data/madrid-sigma-ambitos.geojson"),
        ]);
        if (sigmaRes.ok && !cancelled) setSigmaData((await sigmaRes.json()) as MadridSigmaDataset);
        if (ambitosRes.ok && !cancelled) {
          const fc = (await ambitosRes.json()) as SectorFeatureCollection;
          setAmbitosGeo(fc);
          setGeoCache((p) => ({ ...p, ambitos: fc }));
        }
      } finally {
        if (!cancelled) setLayerLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showSigma, ambitosGeo]);

  /** Popups SIGMA: BOCM + métricas solo si hace falta. */
  useEffect(() => {
    if (!showSigma || (bocmByExp && metricsBundle)) return;
    let cancelled = false;
    (async () => {
      const [bocmRes, mb] = await Promise.all([
        bocmByExp ? Promise.resolve(null) : fetch("/data/madrid-sigma-bocm-projects.json"),
        metricsBundle ? Promise.resolve(null) : loadSigmaMetricsBundle(),
      ]);
      if (!cancelled) {
        if (bocmRes?.ok) {
          const j = (await bocmRes.json()) as { byExpediente?: Record<string, SigmaBocmPopupLink[]> };
          if (j.byExpediente) setBocmByExp(j.byExpediente);
        }
        if (mb) setMetricsBundle(mb);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showSigma, bocmByExp, metricsBundle]);

  useEffect(() => {
    if (mapMode === "ambitos" || mapMode === "ip" || geoCache[mapMode]) return;
    const ac = new AbortController();
    setLayerLoading(true);
    (async () => {
      try {
        const res = await fetch(SIGMA_LAYER_URL[mapMode], { signal: ac.signal });
        if (!res.ok) throw new Error(String(res.status));
        const fc = (await res.json()) as SectorFeatureCollection;
        if (!ac.signal.aborted) setGeoCache((p) => ({ ...p, [mapMode]: fc }));
      } catch {
        /* capa opcional */
      } finally {
        if (!ac.signal.aborted) setLayerLoading(false);
      }
    })();
    return () => ac.abort();
  }, [mapMode, geoCache]);

  const suggestions = useMemo(() => {
    const nq = norm(q.trim());
    if (nq.length < 2) return [];
    return searchIndex
      .filter((item) =>
        norm([item.label, item.direccion, item.distrito, item.barrio, item.ndp].join(" ")).includes(nq),
      )
      .slice(0, 10);
  }, [q, searchIndex]);

  const filteredUbicGeo = useMemo(() => {
    if (!ubicGeo) return null;
    let feats = filterUbicacionesMadridCapital(ubicGeo).features;
    const nq = norm(q.trim());
    if (nq.length >= 2) {
      const ndpSet = new Set(
        searchIndex
          .filter((item) =>
            norm([item.label, item.direccion, item.distrito, item.ndp].join(" ")).includes(nq),
          )
          .map((i) => i.ndp),
      );
      feats = feats.filter((f) => ndpSet.has(f.properties.ndp));
    }
    if (dateFilterActive) {
      feats = feats.filter((f) =>
        passesMapDateRange(ubicacionActivityMs(f.properties), dateRange),
      );
    }
    if (showUbicaciones && licenciaTipoFilterActive) {
      feats = feats.filter((f) =>
        passesLicenciaTipoFilter(f.properties.ultimaLicenciaTipo, licenciaTiposEnabled),
      );
    }
    feats = filterPointFeaturesInView(feats, mapBounds);
    return { ...ubicGeo, features: feats };
  }, [
    ubicGeo,
    q,
    searchIndex,
    mapBounds,
    dateFilterActive,
    dateRange,
    showUbicaciones,
    licenciaTipoFilterActive,
    licenciaTiposEnabled,
  ]);

  const polygonGeo =
    mapMode === "ambitos"
      ? ambitosGeo ?? geoCache.ambitos ?? null
      : mapMode === "ip"
        ? ipGeo
        : geoCache[mapMode] ?? null;

  const sigmaGeoFiltered = useMemo(() => {
    if (!polygonGeo?.features?.length) return null;
    const nq = normSearch(q.trim());
    let feats = polygonGeo.features;
    if (nq) {
      feats = feats.filter((f) => {
        const p = (f.properties || {}) as Record<string, unknown>;
        return (
          normSearch(String(p.EXP_TX_DENOM || "")).includes(nq) ||
          normSearch(String(p.EXP_TX_NUMERO || "")).includes(nq) ||
          normSearch(String(p.FIG_TX_ETIQ || "")).includes(nq)
        );
      });
    }
    if (sigmaMapOnlyWithPortal && bocmByExp) {
      feats = feats.filter((f) =>
        sigmaPassesPortalLink((f.properties || {}) as Record<string, unknown>, bocmByExp),
      );
    }
    if (dateFilterActive) {
      feats = feats.filter((f) =>
        passesMapDateRange(
          sigmaFeatureActivityMs((f.properties || {}) as Record<string, unknown>),
          dateRange,
        ),
      );
    }
    if (!feats.length) return { type: "FeatureCollection" as const, features: [] };
    if (!showHugeSigmaPolygons) {
      const { visible } = filterSigmaMapFeaturesByBBox(
        { type: "FeatureCollection", features: feats },
        SIGMA_MAP_DEFAULT_MAX_BBOX_KM2,
      );
      return visible;
    }
    const fc = { type: "FeatureCollection" as const, features: feats };
    return filterPolygonFeaturesInView(fc, mapBounds);
  }, [
    polygonGeo,
    q,
    sigmaMapOnlyWithPortal,
    bocmByExp,
    dateFilterActive,
    dateRange,
    showHugeSigmaPolygons,
    mapBounds,
  ]);

  const mapStatsHint = useMemo(() => {
    const parts: string[] = [];
    if (showUbicaciones && filteredUbicGeo) {
      parts.push(`${filteredUbicGeo.features.length.toLocaleString("es-ES")} edificios en vista`);
    }
    if (showSigma && sigmaGeoFiltered) {
      parts.push(ambitosProyectosEnVista(sigmaGeoFiltered.features.length));
    }
    if (!mapBounds && !dataReady.ubic) return "Cargando mapa…";
    if (!mapBounds) return "Acercando datos a la zona visible…";
    if (dateFilterActive) parts.push("filtro de fecha activo");
    if (showUbicaciones && licenciaTipoFilterActive) parts.push("filtro por tipo de licencia");
    return parts.length ? parts.join(" · ") : "Sin datos en esta zona";
  }, [
    showUbicaciones,
    filteredUbicGeo,
    showSigma,
    sigmaGeoFiltered,
    mapBounds,
    dataReady.ubic,
    dateFilterActive,
    licenciaTipoFilterActive,
  ]);

  const onBoundsChange = useCallback((b: MapBounds) => {
    setMapBounds(b);
  }, []);

  const sigmaPopupOptions = useMemo(
    () => ({
      sigmaBocmByExpediente: bocmByExp ?? undefined,
      sigmaMetricsByExpediente: metricsBundle?.byExpediente,
    }),
    [bocmByExp, metricsBundle],
  );

  const goUbicacion = useCallback(
    (ndp: string) => router.push(ubicacionPath(ndp)),
    [router],
  );

  const pickSuggestion = useCallback((item: UbicacionSearchItem) => {
    setQ(item.label);
    setHighlightNdp(item.ndp);
    setOpenSuggest(false);
  }, []);

  if (err) {
    return (
      <Div className="flex flex-1 items-center justify-center p-6">
        <p className="max-w-md rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {err}
        </p>
      </Div>
    );
  }

  return (
    <Div className="relative h-full w-full">
      <div className="absolute inset-0">
        <MadridUnifiedMap
          ubicacionesGeojson={showUbicaciones && dataReady.ubic ? filteredUbicGeo : null}
          sigmaGeojson={showSigma ? sigmaGeoFiltered : null}
          highlightNdp={highlightNdp}
          onSelectNdp={goUbicacion}
          sigmaPopupOptions={sigmaPopupOptions}
          showUbicaciones={showUbicaciones && dataReady.ubic}
          showSigma={showSigma && !layerLoading}
          onBoundsChange={onBoundsChange}
          statsHint={
            !dataReady.ubic
              ? "Cargando edificios…"
              : mapStatsHint
          }
          className="h-full w-full"
        />
        {!dataReady.ubic ? (
          <Div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-100/60 backdrop-blur-[1px]">
            <p className="rounded-lg bg-white/90 px-4 py-2 text-sm text-slate-600 shadow-sm">
              Cargando edificios…
            </p>
          </Div>
        ) : null}
      </div>

      <MapLayerToolbar
        showSigma={showSigma}
        onToggleSigma={() => setShowSigma((v) => !v)}
        showUbicaciones={showUbicaciones}
        onToggleUbicaciones={() => setShowUbicaciones((v) => !v)}
        mapMode={mapMode}
        onMapModeChange={setMapMode}
        layerLoading={layerLoading}
      />

      {!panelOpen ? (
        <button
          type="button"
          onClick={() => setPanelOpen(true)}
          className="absolute bottom-5 right-5 z-[1100] rounded-full border border-slate-200 bg-white/95 px-4 py-2.5 text-sm font-semibold text-slate-800 shadow-lg backdrop-blur-sm sm:bottom-auto sm:right-auto sm:left-4 sm:top-4"
        >
          Filtros
        </button>
      ) : null}

      {panelOpen ? (
        <>
          <button
            type="button"
            aria-label="Cerrar filtros"
            className="absolute inset-0 z-[1040] bg-slate-900/40 sm:hidden"
            onClick={() => setPanelOpen(false)}
          />
          <aside className="absolute inset-x-0 bottom-0 z-[1050] flex max-h-[min(72dvh,28rem)] flex-col overflow-hidden rounded-t-2xl border border-slate-200/90 border-b-0 bg-white shadow-xl sm:inset-x-auto sm:bottom-auto sm:left-4 sm:top-4 sm:max-h-[calc(100%-2rem)] sm:w-[min(calc(100%-1.5rem),22rem)] sm:rounded-2xl sm:border-b">
        <div className="flex shrink-0 justify-center border-b border-slate-100 py-2 sm:hidden">
          <span className="h-1 w-10 rounded-full bg-slate-300" aria-hidden />
        </div>
        <div className="flex items-start justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <div className="min-w-0">
            <h1 className="text-lg font-bold tracking-tight text-slate-900">Madrid</h1>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-600">
              Activa capas arriba del mapa. Busca aquí; clic en ámbito → ficha del proyecto, en punto → ubicación.
            </p>
          </div>
          <button
            type="button"
            aria-label="Cerrar filtros"
            onClick={() => setPanelOpen(false)}
            className="shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <span className="sr-only">Cerrar</span>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
              <path
                d="M5 5l10 10M15 5L5 15"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
          <label className="block space-y-1">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Buscar
            </span>
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setOpenSuggest(true);
                setHighlightNdp(null);
              }}
              onFocus={() => setOpenSuggest(true)}
              placeholder="Dirección, proyecto, barrio…"
              className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/20"
              autoComplete="off"
            />
          </label>

          {openSuggest && suggestions.length > 0 ? (
            <ul className="max-h-40 overflow-auto rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-inner">
              {suggestions.map((item) => (
                <li key={item.ndp}>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left hover:bg-[var(--portal-accent-soft)]"
                    onMouseDown={() => pickSuggestion(item)}
                  >
                    <span className="font-medium text-slate-900">{item.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          {highlightNdp ? (
            <button
              type="button"
              onClick={() => goUbicacion(highlightNdp)}
              className="w-full rounded-lg bg-[var(--portal-accent)] py-2.5 text-sm font-semibold text-white hover:bg-[var(--portal-accent-hover)]"
            >
              Ver ficha ubicación
            </button>
          ) : null}

          {showUbicaciones ? (
            <fieldset className="space-y-2 border-t border-slate-100 pt-3">
              <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Tipo de licencia
              </legend>
              <p className="text-xs leading-relaxed text-slate-500">
                Según la licencia más reciente de cada edificio. Desmarca las que no quieras ver.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setLicenciaTiposEnabled(allLicenciaTiposEnabled())}
                  className="text-xs font-medium text-[var(--portal-accent)] hover:underline"
                >
                  Todas
                </button>
                <button
                  type="button"
                  onClick={() => setLicenciaTiposEnabled(new Set())}
                  className="text-xs font-medium text-slate-500 hover:underline"
                >
                  Ninguna
                </button>
              </div>
              <div className="max-h-44 space-y-1.5 overflow-y-auto pr-1">
                {LICENCIA_TIPOS_FILTRABLES.map((cat) => {
                  const cfg = LICENCIA_MAPA_CONFIG[cat];
                  const on = licenciaTiposEnabled.has(cat);
                  return (
                    <label
                      key={cat}
                      className="flex cursor-pointer items-center gap-2 text-xs text-slate-700"
                    >
                      <input
                        type="checkbox"
                        className="accent-[var(--portal-accent)]"
                        checked={on}
                        onChange={() => toggleLicenciaTipo(cat)}
                      />
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-white"
                        style={{ backgroundColor: cfg.bg, boxShadow: `0 0 0 1px ${cfg.ring}` }}
                        aria-hidden
                      />
                      <span className="leading-snug">{cfg.label}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          ) : null}

          <fieldset className="space-y-2 border-t border-slate-100 pt-3">
            <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Fecha
            </legend>
            <p className="text-xs leading-relaxed text-slate-500">
              Última licencia del edificio o última actividad del proyecto. Sin fecha no aparece si
              filtras.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <label className="block space-y-1 text-xs text-slate-600">
                <span>Desde</span>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/20"
                />
              </label>
              <label className="block space-y-1 text-xs text-slate-600">
                <span>Hasta</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/20"
                />
              </label>
            </div>
            {dateFilterActive ? (
              <button
                type="button"
                onClick={() => {
                  setDateFrom("");
                  setDateTo("");
                }}
                className="text-xs font-medium text-[var(--portal-accent)] hover:underline"
              >
                Quitar filtro de fecha
              </button>
            ) : null}
          </fieldset>

          {showSigma ? (
            <fieldset className="space-y-2 border-t border-slate-100 pt-3">
              <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Proyectos
              </legend>
              <label className="flex cursor-pointer items-start gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  className="mt-0.5 accent-[var(--portal-accent)]"
                  checked={sigmaMapOnlyWithPortal}
                  onChange={(e) => setSigmaMapOnlyWithPortal(e.target.checked)}
                />
                Solo con anuncio BOCM
              </label>
              <label className="flex cursor-pointer items-start gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  className="mt-0.5 accent-[var(--portal-accent)]"
                  checked={showHugeSigmaPolygons}
                  onChange={(e) => setShowHugeSigmaPolygons(e.target.checked)}
                />
                Polígonos muy extensos
              </label>
              {layerLoading ? (
                <p className="text-xs text-slate-400">Cargando capa…</p>
              ) : null}
            </fieldset>
          ) : null}
        </div>

        {sigmaData?.counts ? (
          <div className="border-t border-slate-100 bg-slate-50/80 px-4 py-2.5 text-[11px] text-slate-500">
            Catálogo: {sigmaData.counts.expedientes_unicos?.toLocaleString("es-ES") ?? "—"} proyectos
            {metricsBundle?.count ? (
              <span> · {metricsBundle.count} con métricas PDF</span>
            ) : null}
          </div>
        ) : null}
          </aside>
        </>
      ) : null}
    </Div>
  );
}
