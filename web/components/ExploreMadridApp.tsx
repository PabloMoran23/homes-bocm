"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { normSearch } from "@/lib/madrid";
import {
  SIGMA_DEFAULT_MIN_YEAR_EXCLUSIVE_2020,
  sigmaPassesMinYearInclusive,
  sigmaPassesPortalLink,
} from "@/lib/madrid-sigma-filters";
import { loadSigmaMetricsBundle, type MadridSigmaMetricsFile } from "@/lib/sigma-metrics";
import { filterSigmaMapFeaturesByBBox, SIGMA_MAP_DEFAULT_MAX_BBOX_KM2 } from "@/lib/sigma-map-geometry";
import type { SigmaBocmPopupLink, SectorFeatureCollection } from "@/lib/sector-geo";
import type { UbicacionSearchItem } from "@/lib/ubicacion";
import { ubicacionPath } from "@/lib/ubicacion";
import type { MadridSigmaDataset } from "@/lib/types";

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

type UbicacionGeo = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      ndp: string;
      direccion: string | null;
      distrito: string | null;
      barrio: string | null;
      licencias: number;
      sigma: number;
    };
  }>;
};

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
  const [ubicGeo, setUbicGeo] = useState<UbicacionGeo | null>(null);
  const [searchIndex, setSearchIndex] = useState<UbicacionSearchItem[]>([]);
  const [sigmaData, setSigmaData] = useState<MadridSigmaDataset | null>(null);
  const [ambitosGeo, setAmbitosGeo] = useState<SectorFeatureCollection | null>(null);
  const [ipGeo, setIpGeo] = useState<SectorFeatureCollection | null>(null);
  const [geoCache, setGeoCache] = useState<Partial<Record<SigmaMapMode, SectorFeatureCollection>>>({});
  const [bocmByExp, setBocmByExp] = useState<Record<string, SigmaBocmPopupLink[]> | null>(null);
  const [metricsBundle, setMetricsBundle] = useState<MadridSigmaMetricsFile | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);

  const [q, setQ] = useState("");
  const [highlightNdp, setHighlightNdp] = useState<string | null>(null);
  const [openSuggest, setOpenSuggest] = useState(false);
  const [showUbicaciones, setShowUbicaciones] = useState(true);
  const [showSigma, setShowSigma] = useState(true);
  const [mapMode, setMapMode] = useState<SigmaMapMode>("ambitos");
  const [layerLoading, setLayerLoading] = useState(false);
  const [showHugeSigmaPolygons, setShowHugeSigmaPolygons] = useState(false);
  const [sigmaMapOnlyWithPortal, setSigmaMapOnlyWithPortal] = useState(false);
  const [sigmaMinYearInclusive, setSigmaMinYearInclusive] = useState<number | null>(
    SIGMA_DEFAULT_MIN_YEAR_EXCLUSIVE_2020,
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mapRes, searchRes, sigmaRes, ambitosRes, ipRes, bocmRes] = await Promise.all([
          fetch("/data/ubicaciones-map.geojson"),
          fetch("/data/ubicaciones-search.json"),
          fetch("/data/madrid-sigma.json"),
          fetch("/data/madrid-sigma-ambitos.geojson"),
          fetch("/data/madrid-sigma-ip.geojson"),
          fetch("/data/madrid-sigma-bocm-projects.json"),
        ]);
        if (!mapRes.ok || !searchRes.ok) throw new Error("ubicaciones");
        if (!cancelled) {
          setUbicGeo((await mapRes.json()) as UbicacionGeo);
          setSearchIndex((await searchRes.json()) as UbicacionSearchItem[]);
        }
        if (sigmaRes.ok && !cancelled) setSigmaData((await sigmaRes.json()) as MadridSigmaDataset);
        if (ambitosRes.ok && !cancelled) {
          const fc = (await ambitosRes.json()) as SectorFeatureCollection;
          setAmbitosGeo(fc);
          setGeoCache((p) => ({ ...p, ambitos: fc }));
        }
        if (ipRes.ok && !cancelled) {
          const fc = (await ipRes.json()) as SectorFeatureCollection;
          setIpGeo(fc);
          setGeoCache((p) => ({ ...p, ip: fc }));
        }
        if (bocmRes.ok && !cancelled) {
          const j = (await bocmRes.json()) as { byExpediente?: Record<string, SigmaBocmPopupLink[]> };
          if (j.byExpediente) setBocmByExp(j.byExpediente);
        }
        const mb = await loadSigmaMetricsBundle();
        if (!cancelled) setMetricsBundle(mb);
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
    const madridOnly = ubicGeo.features.filter((f) => {
      const [lng, lat] = f.geometry.coordinates;
      return lat >= 39.5 && lat <= 41.2 && lng >= -4.5 && lng <= -3.0;
    });
    const base = { ...ubicGeo, features: madridOnly };
    const nq = norm(q.trim());
    if (nq.length < 2) return base;
    const ndpSet = new Set(
      searchIndex
        .filter((item) =>
          norm([item.label, item.direccion, item.distrito, item.ndp].join(" ")).includes(nq),
        )
        .map((i) => i.ndp),
    );
    return {
      ...base,
      features: base.features.filter((f) => ndpSet.has(f.properties.ndp)),
    };
  }, [ubicGeo, q, searchIndex]);

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
    if (sigmaMinYearInclusive != null) {
      feats = feats.filter((f) =>
        sigmaPassesMinYearInclusive(
          (f.properties || {}) as Record<string, unknown>,
          sigmaMinYearInclusive,
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
    return { type: "FeatureCollection" as const, features: feats };
  }, [
    polygonGeo,
    q,
    sigmaMapOnlyWithPortal,
    bocmByExp,
    sigmaMinYearInclusive,
    showHugeSigmaPolygons,
  ]);

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

  if (!ubicGeo) {
    return (
      <Div className="flex flex-1 items-center justify-center bg-slate-100">
        <p className="text-sm text-slate-500">Cargando Madrid…</p>
      </Div>
    );
  }

  return (
    <Div className="relative flex min-h-0 flex-1 flex-col">
      <MadridUnifiedMap
        ubicacionesGeojson={showUbicaciones ? filteredUbicGeo : null}
        sigmaGeojson={showSigma ? sigmaGeoFiltered : null}
        highlightNdp={highlightNdp}
        onSelectNdp={goUbicacion}
        sigmaPopupOptions={sigmaPopupOptions}
        showUbicaciones={showUbicaciones}
        showSigma={showSigma && !layerLoading}
        className="absolute inset-0"
      />

      <button
        type="button"
        onClick={() => setPanelOpen((o) => !o)}
        className="absolute left-3 top-3 z-[1100] rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs font-semibold text-slate-700 shadow-md backdrop-blur-sm sm:hidden"
      >
        {panelOpen ? "Ocultar" : "Filtros"}
      </button>

      <aside
        className={`absolute left-3 top-3 z-[1050] flex max-h-[calc(100%-1.5rem)] w-[min(calc(100%-1.5rem),22rem)] flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white/95 shadow-xl backdrop-blur-md transition-transform sm:top-4 sm:max-h-[calc(100%-2rem)] ${
          panelOpen ? "translate-x-0" : "-translate-x-[110%] sm:translate-x-0"
        }`}
      >
        <div className="border-b border-slate-100 px-4 py-3">
          <h1 className="text-lg font-bold tracking-tight text-slate-900">Madrid</h1>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-600">
            Expedientes SIGMA y edificios con licencias. Clic en polígono → ficha expediente; en punto →
            ubicación.
          </p>
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
              placeholder="Dirección, expediente, barrio…"
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

          <fieldset className="space-y-2">
            <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Capas
            </legend>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="accent-[var(--portal-accent)]"
                checked={showSigma}
                onChange={(e) => setShowSigma(e.target.checked)}
              />
              Expedientes SIGMA
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="accent-[var(--portal-accent)]"
                checked={showUbicaciones}
                onChange={(e) => setShowUbicaciones(e.target.checked)}
              />
              Edificios (licencias)
            </label>
          </fieldset>

          {showSigma ? (
            <fieldset className="space-y-2 border-t border-slate-100 pt-3">
              <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                SIGMA · geometría
              </legend>
              {(["ambitos", "ip", "ad", "gestion", "urbanizacion"] as const).map((mode) => (
                <label key={mode} className="flex cursor-pointer items-center gap-2 text-xs text-slate-700">
                  <input
                    type="radio"
                    name="sigma-layer"
                    className="accent-[var(--portal-accent)]"
                    checked={mapMode === mode}
                    onChange={() => setMapMode(mode)}
                  />
                  {mode === "ambitos"
                    ? "Todos los ámbitos (mapeados)"
                    : mode === "ip"
                      ? "Información pública"
                      : mode === "ad"
                        ? "Planeamiento AD"
                        : mode === "gestion"
                          ? "Gestión"
                          : "Urbanización"}
                </label>
              ))}
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
              <label className="flex items-center gap-2 text-xs text-slate-600">
                <span className="shrink-0">Desde año</span>
                <select
                  value={sigmaMinYearInclusive === null ? "" : String(sigmaMinYearInclusive)}
                  onChange={(e) =>
                    setSigmaMinYearInclusive(e.target.value === "" ? null : Number(e.target.value))
                  }
                  className="rounded border border-slate-200 px-1 py-0.5 text-xs"
                >
                  <option value="">Todos</option>
                  <option value="2021">2021</option>
                  <option value="2020">2020</option>
                  <option value="2018">2018</option>
                </select>
              </label>
              {layerLoading ? (
                <p className="text-xs text-slate-400">Cargando capa…</p>
              ) : null}
            </fieldset>
          ) : null}
        </div>

        {sigmaData?.counts ? (
          <div className="border-t border-slate-100 bg-slate-50/80 px-4 py-2.5 text-[11px] text-slate-500">
            Catálogo: {sigmaData.counts.expedientes_unicos?.toLocaleString("es-ES") ?? "—"} expedientes
            {metricsBundle?.count ? (
              <span> · {metricsBundle.count} con métricas PDF</span>
            ) : null}
          </div>
        ) : null}
      </aside>
    </Div>
  );
}

function motion({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={className}>{children}</div>;
}
