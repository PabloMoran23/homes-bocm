"use client";

import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { portalDensityCamera, PORTAL_INITIAL_MAX_ZOOM } from "@/lib/map-portal-camera";
import { useMunicipalityBoundary } from "@/lib/use-municipality-boundary";
import { scatterApproximateProjects } from "@/lib/map-municipality-placement";
import { usePortalMapData } from "@/lib/use-portal-map-data";
import { useDebouncedValue } from "@/lib/use-debounced-value";

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
import type { UbicacionMapProperties, UbicacionSearchItem } from "@/lib/ubicacion";
import { ubicacionPath } from "@/lib/ubicacion";
import type { MadridSigmaDataset } from "@/lib/types";
import type { ActuacionQueCodigo } from "@/lib/actuacion-edificio";
import { getActuacionQueMapStyle } from "@/lib/actuacion-que-config";
import {
  ACTUACION_QUE_FILTRABLES,
  allActuacionQueEnabled,
  passesActuacionQueFilter,
} from "@/lib/map-licencia-filters";
import { SigmaClassificationFilterPanel } from "@/components/sigma/SigmaClassificationFilterPanel";
import {
  allSigmaClassificationEnabled,
  buildSigmaClassificationAllowedSet,
  buildSigmaClassificationAxisMeta,
  isSigmaClassificationFilterActive,
  type MadridSigmaClasificacionFile,
  sigmaExpedienteKeyFromFeatureProps,
  type SigmaClassificationFilters,
} from "@/lib/sigma-classification-filters";
import {
  filterUbicacionesMadridCapital,
  type UbicacionesMapGeoJson,
} from "@/lib/madrid-ubicaciones-map";
import {
  featureCollectionBounds,
  type CmMunicipioOption,
  type CmPortalProyectoProps,
} from "@/lib/cm-portal-geo";
import { MapCatalogPanel } from "@/components/map/MapCatalogPanel";
import { isCmMapScope } from "@/lib/map-scope";
import { fetchDominioJson, fetchDominioOrStatic } from "@/lib/dominio-fetch";
import {
  MAP_CM_MUNICIPIOS_API,
  bboxFetchKey,
  mapSigmaQuery,
  mapUbicacionesQuery,
  SEARCH_UBICACIONES_API,
  shouldLoadSigmaPolygons,
  SIGMA_LAYER_STATIC,
  SIGMA_MAP_CARDS_API,
  sigmaPolygonLimit,
} from "@/lib/map-live-urls";
import { MapMunicipioGate, type MapMunicipioSelection } from "@/components/map/MapMunicipioGate";
import { MapProjectSpotlightCard } from "@/components/MapProjectSpotlightCard";
import { buildLicenseMapSpotlightItem, buildPortalMapSpotlightItem, buildMapProjectSpotlightItem } from "@/lib/map-project-spotlight";
import type { SigmaMapCardSlice } from "@/lib/map-project-spotlight";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { sigmaFichaGrupoFromSlug } from "@/lib/sigma-ficha-path";
import { ambitosProyectosEnVista, PROYECTOS } from "@/lib/ui-labels";

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
  layerLoading,
}: {
  showSigma: boolean;
  onToggleSigma: () => void;
  showUbicaciones: boolean;
  onToggleUbicaciones: () => void;
  layerLoading: boolean;
}) {
  return (
    <div
      className="pointer-events-none absolute inset-x-3 top-3 z-[1100] flex justify-center sm:inset-x-auto sm:left-1/2 sm:right-auto sm:top-4 sm:-translate-x-1/2 sm:px-0"
      role="toolbar"
      aria-label="Capas del mapa"
    >
      <div
        className="pointer-events-auto grid w-full max-w-[min(100%,18.5rem)] grid-cols-2 gap-1 rounded-xl border border-white/90 bg-white p-1 shadow-lg md:bg-white/95 md:backdrop-blur-md sm:w-auto sm:max-w-none"
        role="group"
        aria-label="Capa visible"
      >
        <button
          type="button"
          aria-pressed={showSigma}
          onClick={onToggleSigma}
          title={PROYECTOS}
          className={`min-w-0 truncate rounded-lg px-2 py-2 text-center text-[11px] font-semibold transition sm:px-4 sm:py-1.5 sm:text-sm ${layerToggleClass(showSigma)}`}
        >
          <span className="sm:hidden">Proyectos</span>
          <span className="hidden sm:inline">{PROYECTOS}</span>
          {layerLoading && showSigma ? (
            <span className="font-normal opacity-80"> …</span>
          ) : null}
        </button>
        <button
          type="button"
          aria-pressed={showUbicaciones}
          onClick={onToggleUbicaciones}
          className={`min-w-0 truncate rounded-lg px-2 py-2 text-center text-[11px] font-semibold transition sm:px-4 sm:py-1.5 sm:text-sm ${layerToggleClass(showUbicaciones)}`}
        >
          Licencias
        </button>
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
  const searchParams = useSearchParams();
  const municipioFromUrl = searchParams.get("municipio")?.trim() || null;
  const cmMapScope = isCmMapScope() || Boolean(municipioFromUrl);
  const sigmaFromUrl = searchParams.get("sigma")?.trim() || null;
  const [ubicGeo, setUbicGeo] = useState<UbicacionesMapGeoJson | null>(null);
  const [searchIndex, setSearchIndex] = useState<UbicacionSearchItem[]>([]);
  const [sigmaData, setSigmaData] = useState<MadridSigmaDataset | null>(null);
  const [ambitosGeo, setAmbitosGeo] = useState<SectorFeatureCollection | null>(null);
  const [ipGeo, setIpGeo] = useState<SectorFeatureCollection | null>(null);
  const [geoCache, setGeoCache] = useState<Partial<Record<SigmaMapMode, SectorFeatureCollection>>>({});
  const [bocmByExp, setBocmByExp] = useState<Record<string, SigmaBocmPopupLink[]> | null>(null);
  const [metricsBundle, setMetricsBundle] = useState<MadridSigmaMetricsFile | null>(null);
  const [clasificacionIndex, setClasificacionIndex] = useState<
    MadridSigmaClasificacionFile["byExpediente"] | null
  >(null);
  const [clasificacionFilters, setClasificacionFilters] = useState<SigmaClassificationFilters | null>(
    null,
  );
  const [err, setErr] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);

  /** En escritorio el panel lateral arranca abierto (solo al montar, sin forzar al redimensionar). */
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (window.matchMedia("(min-width: 1024px)").matches) setPanelOpen(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);



  const [q, setQ] = useState("");
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogCategory, setCatalogCategory] = useState("");
  const debouncedQ = useDebouncedValue(q, 300);
  const [highlightNdp, setHighlightNdp] = useState<string | null>(null);
  const [selectedSigmaGrupo, setSelectedSigmaGrupo] = useState<string | null>(null);
  const [selectedLicense, setSelectedLicense] = useState<UbicacionMapProperties | null>(null);
  const [selectedPortalProject, setSelectedPortalProject] = useState<{ token: number; project: CmPortalProyectoProps } | null>(null);
  const [mapCardsByExp, setMapCardsByExp] = useState<Record<string, SigmaMapCardSlice> | null>(
    null,
  );
  const [openSuggest, setOpenSuggest] = useState(false);
  const [showUbicaciones, setShowUbicaciones] = useState(false);
  const [showSigma, setShowSigma] = useState(true);
  const [mapBounds, setMapBounds] = useState<MapBounds | null>(null);
  const liveBounds = useDebouncedValue(mapBounds, 450);
  /** One debounce after moveend; the hook deduplicates quantized URLs. */
  const portalBoundsDebounced = useDebouncedValue(mapBounds, 250);
  const [dataReady, setDataReady] = useState({ ubic: true, search: true });
  const [ubicLoading, setUbicLoading] = useState(false);
  const [mapMode, setMapMode] = useState<SigmaMapMode>("ambitos");
  const [layerLoading, setLayerLoading] = useState(false);
  const [showHugeSigmaPolygons, setShowHugeSigmaPolygons] = useState(false);
  const [sigmaMapOnlyWithPortal, setSigmaMapOnlyWithPortal] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [gateOpen, setGateOpen] = useState(cmMapScope);
  const [portalQuery, setPortalQuery] = useState<{
    slug: string;
    nombre: string;
    from: string;
    to: string;
    west: number | null;
    south: number | null;
    east: number | null;
    north: number | null;
    token: number;
    initialFrame: ReturnType<typeof portalDensityCamera>;
  } | null>(null);

  const selectMunicipio = useCallback(({ municipio, from, to }: MapMunicipioSelection) => {
    setDateFrom(from);
    setDateTo(to);
    setMapBounds(null);
    setPortalQuery({
      slug: municipio.slug,
      nombre: municipio.nombre,
      from,
      to,
      west: municipio.west,
      south: municipio.south,
      east: municipio.east,
      north: municipio.north,
      token: Date.now(),
      initialFrame: portalDensityCamera(municipio),
    });
    setSelectedLicense(null);
    if (municipio.slug !== "madrid") { setShowUbicaciones(false); setShowSigma(true); }
    setCatalogQuery("");
    setCatalogCategory("");
    setGateOpen(false);
  }, []);

  useEffect(() => {
    if (!municipioFromUrl) return;
    const controller = new AbortController();
    void fetch(MAP_CM_MUNICIPIOS_API, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error("municipios"); return response.json(); })
      .then((data: { municipios?: CmMunicipioOption[] }) => {
        const municipio = data.municipios?.find(item => item.slug === municipioFromUrl);
        if (municipio) selectMunicipio({ municipio, from: "", to: "" });
      })
      .catch(() => { /* The existing selector offers retry if the catalog is unavailable. */ });
    return () => controller.abort();
  }, [municipioFromUrl, selectMunicipio]);

  useEffect(() => {
    if (!sigmaFromUrl || cmMapScope) return;
    setSelectedSigmaGrupo(sigmaFichaGrupoFromSlug(sigmaFromUrl));
    setShowSigma(true);
  }, [sigmaFromUrl, cmMapScope]);

  const dateRange = useMemo(
    () => mapDateRangeFromInputs(dateFrom, dateTo),
    [dateFrom, dateTo],
  );
  const dateFilterActive = Boolean(dateFrom || dateTo);
  const [actuacionQueEnabled, setActuacionQueEnabled] = useState<Set<ActuacionQueCodigo>>(
    () => allActuacionQueEnabled(),
  );
  const actuacionQueFilterActive =
    actuacionQueEnabled.size < ACTUACION_QUE_FILTRABLES.length;
  const clasificacionAxisMeta = useMemo(
    () => (clasificacionIndex ? buildSigmaClassificationAxisMeta(clasificacionIndex) : null),
    [clasificacionIndex],
  );
  const clasificacionFilterActive = useMemo(
    () =>
      clasificacionAxisMeta && clasificacionFilters
        ? isSigmaClassificationFilterActive(clasificacionFilters, clasificacionAxisMeta.totals)
        : false,
    [clasificacionFilters, clasificacionAxisMeta],
  );
  const deferredClasificacionFilters = useDeferredValue(clasificacionFilters);
  const clasificacionMapPending =
    clasificacionFilters !== deferredClasificacionFilters && clasificacionFilterActive;

  const clasificacionAllowedSet = useMemo(() => {
    if (!clasificacionIndex || !deferredClasificacionFilters || !clasificacionAxisMeta) return null;
    return buildSigmaClassificationAllowedSet(
      clasificacionIndex,
      deferredClasificacionFilters,
      clasificacionAxisMeta.totals,
    );
  }, [clasificacionIndex, deferredClasificacionFilters, clasificacionAxisMeta]);

  const toggleActuacionQue = useCallback((codigo: ActuacionQueCodigo) => {
    setActuacionQueEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(codigo)) next.delete(codigo);
      else next.add(codigo);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!showUbicaciones || !liveBounds) return;
    let cancelled = false;
    setUbicLoading(true);
    (async () => {
      try {
        let res = await fetch(mapUbicacionesQuery(liveBounds));
        if (!res.ok) {
          res = await fetch("/data/ubicaciones-map.geojson");
        }
        if (!res.ok) throw new Error("ubicaciones");
        const fc = (await res.json()) as UbicacionesMapGeoJson;
        if (!cancelled) {
          setUbicGeo(fc);
          setDataReady((prev) => ({ ...prev, ubic: true }));
        }
      } catch {
        if (!cancelled) {
          setErr("No hemos podido cargar las licencias de esta zona. Prueba a recargar.");
        }
      } finally {
        if (!cancelled) setUbicLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showUbicaciones, liveBounds]);

  useEffect(() => {
    const nq = q.trim();
    if (nq.length < 2) {
      setSearchIndex([]);
      return;
    }
    let cancelled = false;
    const t = window.setTimeout(() => {
      (async () => {
        try {
          const res = await fetch(`${SEARCH_UBICACIONES_API}?q=${encodeURIComponent(nq)}`);
          if (!res.ok) return;
          const rows = (await res.json()) as UbicacionSearchItem[];
          if (!cancelled && Array.isArray(rows)) setSearchIndex(rows);
        } catch {
          /* búsqueda opcional */
        }
      })();
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [q]);

  const portal = usePortalMapData(cmMapScope, portalQuery, mapBounds ? portalBoundsDebounced : null);
  const municipalityBoundary = useMunicipalityBoundary(portalQuery, cmMapScope && !gateOpen);
  const showApproximateProjects = portal.meta?.proyectosConUbicacion === 0;
  const approximateMarkers = useMemo(() => {
    if (!portalQuery || !showApproximateProjects) return null;
    const f = portalQuery.initialFrame;
    return scatterApproximateProjects(portal.approx, municipalityBoundary, [(f.west + f.east) / 2, (f.south + f.north) / 2]);
  }, [portal.approx, municipalityBoundary, portalQuery, showApproximateProjects]);
  const catalogProjects = useMemo(() => {
    const unique = new Map<string, CmPortalProyectoProps>();
    for (const feature of [...(portal.approx?.features ?? []), ...(portal.polygons?.features ?? []), ...(portal.points?.features ?? [])]) unique.set(feature.properties.id, feature.properties);
    return [...unique.values()].map(project => {
      const group = expedienteGrupoKeyFromVariant(/^\d+-\d+-\d+$/.test(project.id) ? project.id.replace(/-/g, "/") : project.id);
      return { project, item: buildPortalMapSpotlightItem(project, clasificacionIndex?.[group]) };
    });
  }, [portal.approx, portal.polygons, portal.points, clasificacionIndex]);
  const otherProjects = catalogProjects.filter(({ item }) => item.approx && !showApproximateProjects).map(({ item }) => item);
  const catalogCategories = useMemo(() => [...new Set(catalogProjects.filter(({ item }) => !item.approx || showApproximateProjects).map(({ item }) => item.categoryLabel))].sort((a, b) => a.localeCompare(b, "es")), [catalogProjects, showApproximateProjects]);
  const catalogFiltered = useMemo(() => catalogProjects.filter(({ project, item }) =>
    (!item.approx || showApproximateProjects) &&
    (!catalogCategory || item.categoryLabel === catalogCategory) &&
    (!catalogQuery.trim() || norm(`${item.title} ${project.id} ${item.resumen}`).includes(norm(catalogQuery.trim())))
  ), [catalogProjects, catalogCategory, catalogQuery, showApproximateProjects]);
  const catalogIds = useMemo(() => new Set(catalogFiltered.map(({ project }) => project.id)), [catalogFiltered]);
  const portalGeo = useMemo(() => portal.points ? { ...portal.points, features: portal.points.features.filter(f => catalogIds.has(f.properties.id)) } : null, [portal.points, catalogIds]);
  const portalPolygonGeo = useMemo(() => portal.polygons ? { ...portal.polygons, features: portal.polygons.features.filter(f => catalogIds.has(f.properties.id)) } : null, [portal.polygons, catalogIds]);
  const portalMapMeta = portal.meta;
  const portalLoading = portal.loading;
  const portalErr = portal.error;

  useEffect(() => {
    if (!cmMapScope || !portalQuery || gateOpen) return;
    if (dateFrom && dateTo && dateFrom > dateTo) return;
    if (dateFrom === portalQuery.from && dateTo === portalQuery.to) return;
    setPortalQuery((current) =>
      current ? { ...current, from: dateFrom, to: dateTo } : current,
    );
  }, [cmMapScope, portalQuery, gateOpen, dateFrom, dateTo]);

  const sigmaFetchKey = bboxFetchKey(liveBounds, liveBounds?.zoom, mapMode);

  /** Catálogo SIGMA (listado) una vez; geometría en vivo por zoom/bbox. */
  useEffect(() => {
    if (cmMapScope) return;
    if (!showSigma || sigmaData) return;
    let cancelled = false;
    (async () => {
      const data = await fetchDominioJson<MadridSigmaDataset>(
        "/api/dominio/madrid-sigma",
        "/data/madrid-sigma.json",
      );
      if (data && !cancelled) setSigmaData(data);
    })();
    return () => {
      cancelled = true;
    };
  }, [showSigma, sigmaData, cmMapScope]);

  useEffect(() => {
    if (cmMapScope) return;
    if (!showSigma) return;
    if (!shouldLoadSigmaPolygons(liveBounds?.zoom, liveBounds)) return;
    let cancelled = false;
    setLayerLoading(true);
    (async () => {
      try {
        const staticFallback = SIGMA_LAYER_STATIC[mapMode] || SIGMA_LAYER_STATIC.ambitos;
        const res = await fetchDominioOrStatic(
          mapSigmaQuery({
            layer: mapMode,
            zoom: liveBounds?.zoom,
            bounds: liveBounds,
            limit: sigmaPolygonLimit(liveBounds?.zoom),
          }),
          staticFallback,
        );
        if (!res?.ok) throw new Error("map-sigma");
        const fc = (await res.json()) as SectorFeatureCollection;
        if (cancelled) return;
        if (mapMode === "ambitos") setAmbitosGeo(fc);
        if (mapMode === "ip") setIpGeo(fc);
        setGeoCache((p) => ({ ...p, [mapMode]: fc }));
      } catch {
        /* capa opcional */
      } finally {
        if (!cancelled) setLayerLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showSigma, mapMode, sigmaFetchKey, cmMapScope]);

  /** El mapa municipal usa los mismos iconos por expediente que la ficha de proyecto. */
  useEffect(() => {
    if (!cmMapScope || !showSigma || clasificacionIndex) return;
    let cancelled = false;
    void fetchDominioJson<MadridSigmaClasificacionFile>(
      "/api/dominio/madrid-sigma-clasificacion",
      "/data/madrid-sigma-clasificacion.json",
    ).then((file) => {
      if (!cancelled && file?.byExpediente) setClasificacionIndex(file.byExpediente);
    });
    return () => { cancelled = true; };
  }, [cmMapScope, showSigma, clasificacionIndex]);

  /** Popups SIGMA: BOCM + métricas + clasificación + tarjetas de mapa. */
  useEffect(() => {
    if (cmMapScope) return;
    if (!showSigma) return;
    if (bocmByExp && metricsBundle && clasificacionIndex && mapCardsByExp) return;
    let cancelled = false;
    (async () => {
      const [bocmJson, mb, clJson, cardsJson] = await Promise.all([
        bocmByExp
          ? Promise.resolve(null)
          : fetchDominioJson<{ byExpediente?: Record<string, SigmaBocmPopupLink[]> }>(
              "/api/dominio/madrid-sigma-bocm",
              "/data/madrid-sigma-bocm-projects.json",
            ),
        metricsBundle ? Promise.resolve(null) : loadSigmaMetricsBundle(),
        clasificacionIndex
          ? Promise.resolve(null)
          : fetchDominioJson<MadridSigmaClasificacionFile>(
              "/api/dominio/madrid-sigma-clasificacion",
              "/data/madrid-sigma-clasificacion.json",
            ),
        mapCardsByExp
          ? Promise.resolve(null)
          : fetchDominioJson<{ byExpediente?: Record<string, SigmaMapCardSlice> }>(
              SIGMA_MAP_CARDS_API,
              "/data/madrid-sigma-map-cards.json",
            ),
      ]);
      if (!cancelled) {
        if (bocmJson?.byExpediente) setBocmByExp(bocmJson.byExpediente);
        if (mb) setMetricsBundle(mb);
        if (clJson?.byExpediente) {
          const byExp = clJson.byExpediente;
          const meta = buildSigmaClassificationAxisMeta(byExp);
          setClasificacionIndex(byExp);
          setClasificacionFilters((prev) => prev ?? allSigmaClassificationEnabled(meta));
        }
        if (cardsJson?.byExpediente) setMapCardsByExp(cardsJson.byExpediente);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showSigma, bocmByExp, metricsBundle, clasificacionIndex, mapCardsByExp, cmMapScope]);

  const suggestions = useMemo(() => searchIndex.slice(0, 10), [searchIndex]);

  const filteredUbicGeo = useMemo(() => {
    if (!ubicGeo) return null;
    let feats = filterUbicacionesMadridCapital(ubicGeo).features;
    const nq = norm(debouncedQ.trim());
    if (nq.length >= 2 && searchIndex.length > 0) {
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
    if (showUbicaciones && actuacionQueFilterActive) {
      feats = feats.filter((f) => passesActuacionQueFilter(f.properties, actuacionQueEnabled));
    }
    return { ...ubicGeo, features: feats };
  }, [
    ubicGeo,
    debouncedQ,
    searchIndex,
    dateFilterActive,
    dateRange,
    showUbicaciones,
    actuacionQueFilterActive,
    actuacionQueEnabled,
  ]);

  const ubicCountInView = useMemo(() => {
    if (!filteredUbicGeo) return 0;
    if (!mapBounds) return filteredUbicGeo.features.length;
    return filterPointFeaturesInView(filteredUbicGeo.features, mapBounds).length;
  }, [filteredUbicGeo, mapBounds]);

  const portalCountInView = useMemo(() => {
    if (!cmMapScope) return 0;
    let n = 0;
    if (portalGeo?.features?.length) {
      const mapped = portalGeo.features.filter(
        (f) =>
          f.properties.coordSource !== "municipio_centroid_jitter" &&
          f.geometry.type === "Point",
      ) as Array<{ geometry: { type: "Point"; coordinates: [number, number] } }>;
      n += mapBounds
        ? filterPointFeaturesInView(mapped, mapBounds).length
        : mapped.length;
    }
    if (portalPolygonGeo?.features?.length) {
      const inView = filterPolygonFeaturesInView(
        portalPolygonGeo as unknown as SectorFeatureCollection,
        mapBounds,
      );
      n += inView.features.length;
    }
    return n;
  }, [portalGeo, portalPolygonGeo, mapBounds, cmMapScope]);

  const polygonGeo =
    mapMode === "ambitos"
      ? ambitosGeo ?? geoCache.ambitos ?? null
      : mapMode === "ip"
        ? ipGeo
        : geoCache[mapMode] ?? null;

  const sigmaGeoFiltered = useMemo(() => {
    if (!polygonGeo?.features?.length) return null;
    const nq = normSearch(debouncedQ.trim());
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
    if (clasificacionAllowedSet) {
      feats = feats.filter((f) => {
        const key = sigmaExpedienteKeyFromFeatureProps((f.properties || {}) as Record<string, unknown>);
        return Boolean(key && clasificacionAllowedSet.has(key));
      });
    }
    if (!feats.length) return { type: "FeatureCollection" as const, features: [] };
    const closeZoom = (mapBounds?.zoom ?? 11) >= 13;
    if (closeZoom && !showHugeSigmaPolygons) {
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
    debouncedQ,
    sigmaMapOnlyWithPortal,
    bocmByExp,
    dateFilterActive,
    dateRange,
    showHugeSigmaPolygons,
    mapBounds,
    clasificacionAllowedSet,
  ]);

  const mapStatsHint = useMemo(() => {
    const parts: string[] = [];
    if (showUbicaciones && filteredUbicGeo) {
      parts.push(`${ubicCountInView.toLocaleString("es-ES")} edificios en vista`);
    }
    if (showSigma && sigmaGeoFiltered) {
      parts.push(ambitosProyectosEnVista(sigmaGeoFiltered.features.length));
    }
    if (cmMapScope && showSigma && (portalGeo || portalPolygonGeo)) {
      parts.push(`${portalCountInView.toLocaleString("es-ES")} con ubicación en mapa`);
      if (portalMapMeta?.proyectosSinUbicacion) {
        parts.push(
          `${portalMapMeta.proyectosSinUbicacion.toLocaleString("es-ES")} sin polígono (no se dibujan)`,
        );
      }
    }
    if (!mapBounds) return "Acercando datos a la zona visible…";
    if (showUbicaciones && ubicLoading) parts.push("cargando licencias");
    if (dateFilterActive) parts.push("filtro de fecha activo");
    if (showUbicaciones && actuacionQueFilterActive) parts.push("filtro por actuación");
    if (showSigma && clasificacionFilterActive) parts.push("filtro por clasificación");
    if (clasificacionMapPending) parts.push("actualizando mapa…");
    return parts.length ? parts.join(" · ") : "Sin datos en esta zona";
  }, [
    showUbicaciones,
    filteredUbicGeo,
    ubicCountInView,
    showSigma,
    sigmaGeoFiltered,
    mapBounds,
    ubicLoading,
    dateFilterActive,
    actuacionQueFilterActive,
    clasificacionFilterActive,
    clasificacionMapPending,
    cmMapScope,
    portalGeo,
    portalPolygonGeo,
    portalMapMeta,
    portalCountInView,
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

  const sigmaCatalogByGrupo = useMemo(() => {
    const map = new Map<
      string,
      NonNullable<MadridSigmaDataset["expedientes"]>[number]
    >();
    for (const e of sigmaData?.expedientes ?? []) {
      if (e.EXP_TX_NUMERO) {
        map.set(expedienteGrupoKeyFromVariant(e.EXP_TX_NUMERO), e);
      }
    }
    return map;
  }, [sigmaData]);

  const selectedSpotlightItem = useMemo(() => {
    if (!selectedSigmaGrupo || cmMapScope) return null;
    const grupo = expedienteGrupoKeyFromVariant(selectedSigmaGrupo);
    return buildMapProjectSpotlightItem({
      expedienteGrupo: grupo,
      catalog: sigmaCatalogByGrupo.get(grupo) ?? null,
      clasificacion: (clasificacionIndex?.[grupo] ?? null) as import("@/lib/sigma-classification").SigmaClassification | null,
      metric: metricsBundle?.byExpediente?.[grupo] ?? null,
      cardSlice: mapCardsByExp?.[grupo] ?? null,
    });
  }, [
    selectedSigmaGrupo,
    cmMapScope,
    sigmaCatalogByGrupo,
    clasificacionIndex,
    metricsBundle,
    mapCardsByExp,
  ]);

  const selectedPortalItem = useMemo(() => {
    if (!selectedPortalProject || selectedPortalProject.token !== portalQuery?.token || !catalogIds.has(selectedPortalProject.project.id)) return null;
    const project = selectedPortalProject.project;
    const group = expedienteGrupoKeyFromVariant(/^\d+-\d+-\d+$/.test(project.id) ? project.id.replace(/-/g, "/") : project.id);
    return buildPortalMapSpotlightItem(project, clasificacionIndex?.[group]);
  }, [selectedPortalProject, portalQuery?.token, clasificacionIndex, catalogIds]);
  const onSelectPortalProject = useCallback((project: CmPortalProyectoProps | null) => {
    if (project) setSelectedLicense(null);
    setSelectedPortalProject(project && portalQuery ? { token: portalQuery.token, project } : null);
    if (project && !window.matchMedia("(min-width: 1024px)").matches) setPanelOpen(false);
  }, [portalQuery]);

  const licenseItem = useMemo(() => selectedLicense && showUbicaciones && (!cmMapScope || portalQuery?.slug === "madrid") ? buildLicenseMapSpotlightItem(selectedLicense) : null, [selectedLicense, showUbicaciones, cmMapScope, portalQuery?.slug]);
  const onSelectLicense = useCallback((license: UbicacionMapProperties | null) => {
    setSelectedLicense(license);
    if (license) {
      setSelectedPortalProject(null);
      setSelectedSigmaGrupo(null);
      if (!window.matchMedia("(min-width: 1024px)").matches) setPanelOpen(false);
    }
  }, []);

  const onSelectSigmaExpediente = useCallback((grupo: string | null) => {
    if (grupo) setSelectedLicense(null);
    setSelectedSigmaGrupo(grupo);
  }, []);

  const goUbicacion = useCallback(
    (ndp: string) => router.push(ubicacionPath(ndp)),
    [router],
  );

  const pickSuggestion = useCallback((item: UbicacionSearchItem) => {
    setQ(item.label);
    setHighlightNdp(item.ndp);
    setOpenSuggest(false);
    setShowUbicaciones(true);
    if (item.lat != null && item.lng != null) {
      const lng = item.lng;
      const lat = item.lat;
      setUbicGeo((prev): UbicacionesMapGeoJson => {
        const feature: UbicacionesMapGeoJson["features"][number] = {
          type: "Feature",
          geometry: { type: "Point", coordinates: [lng, lat] },
          properties: {
            ndp: item.ndp,
            direccion: item.direccion,
            distrito: item.distrito,
            barrio: item.barrio,
            licencias: 0,
            sigma: 0,
          },
        };
        const features = prev?.features.some((f) => f.properties.ndp === item.ndp)
          ? prev.features
          : [...(prev?.features ?? []), feature];
        return { type: "FeatureCollection", features };
      });
    }
  }, []);

  const listFrame =
    portalQuery &&
    portalQuery.west != null &&
    portalQuery.south != null &&
    portalQuery.east != null &&
    portalQuery.north != null
      ? {
          west: portalQuery.west,
          south: portalQuery.south,
          east: portalQuery.east,
          north: portalQuery.north,
          token: portalQuery.token,
        }
      : null;
  const polygonFrame = useMemo(() => {
    if (!portalQuery) return null;
    const bounds = featureCollectionBounds(portalPolygonGeo);
    if (!bounds) return null;
    return { ...bounds, token: portalQuery.token + 1, tight: true };
  }, [portalPolygonGeo, portalQuery]);
  const initialPortalFrame = portalQuery
    ? { ...portalQuery.initialFrame, token: portalQuery.token + 1, tight: true, maxZoom: PORTAL_INITIAL_MAX_ZOOM, padding: 16 }
    : null;
  const focusFrame = cmMapScope ? initialPortalFrame : listFrame ?? polygonFrame;
  const portalHasPolygons = (portalPolygonGeo?.features?.length ?? 0) > 0;
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
      <div className={`absolute inset-0 ${cmMapScope && panelOpen && !gateOpen ? "lg:left-[350px]" : ""}`}>
        <MadridUnifiedMap
          ubicacionesGeojson={showUbicaciones && dataReady.ubic ? filteredUbicGeo : null}
          sigmaGeojson={showSigma ? sigmaGeoFiltered : null}
          portalHints={cmMapScope && showSigma && !catalogQuery && !catalogCategory ? portal.hints : null}
          portalGeojson={cmMapScope && showSigma ? portalGeo : null}
          portalPolygonGeojson={cmMapScope && showSigma ? portalPolygonGeo : null}
          showExplorationHints={cmMapScope && portalMapMeta?.truncated === true && !catalogQuery && !catalogCategory}
          municipalityBoundary={municipalityBoundary}
          portalApproxGeojson={cmMapScope && showSigma && approximateMarkers ? { ...approximateMarkers, features: approximateMarkers.features.filter(f => catalogIds.has(f.properties.id)) } : null}
          highlightNdp={highlightNdp}
          onSelectNdp={goUbicacion}
          sigmaPopupOptions={sigmaPopupOptions}
          sigmaClassificationIndex={clasificacionIndex}
          showUbicaciones={showUbicaciones && dataReady.ubic}
          showSigma={showSigma}
          showPortal={cmMapScope && showSigma && portal.ready}
          mapScope={cmMapScope ? "cm" : "madrid"}
          focusFrame={focusFrame}
          onBoundsChange={onBoundsChange}
          statsHint={
            cmMapScope && portalLoading
              ? `Cargando ${portalQuery?.nombre ?? "el municipio"}…`
              : cmMapScope && !portalQuery
                ? "Elige un municipio para ver sus proyectos."
                : mapStatsHint
          }
          className="h-full w-full"
          fitToData={false}
          initialView="explore"
          sigmaCardSelection={!cmMapScope && showSigma}
          selectedSigmaExpediente={selectedSigmaGrupo}
          onSelectSigmaExpediente={onSelectSigmaExpediente}
          onSelectPortalProject={onSelectPortalProject}
          selectedPortalProjectId={selectedPortalItem?.id}
          onSelectLicense={onSelectLicense}
          selectedLicenseNdp={licenseItem ? selectedLicense?.ndp : null}
        />
        {licenseItem && !gateOpen ? <MapProjectSpotlightCard item={licenseItem} visible variant="explore" onClose={() => setSelectedLicense(null)} /> : null}
        {!cmMapScope && showSigma ? (
          <MapProjectSpotlightCard
            item={selectedSpotlightItem}
            visible={selectedSpotlightItem != null}
            variant="explore"
            onClose={() => setSelectedSigmaGrupo(null)}
          />
        ) : null}
        {cmMapScope && showSigma && !gateOpen ? (
          <MapProjectSpotlightCard item={selectedPortalItem} visible={selectedPortalItem != null} variant="explore" onClose={() => setSelectedPortalProject(null)} />
        ) : null}
      </div>

      {!cmMapScope ? (<MapLayerToolbar
        showSigma={showSigma}
        onToggleSigma={() => setShowSigma((v) => !v)}
        showUbicaciones={showUbicaciones}
        onToggleUbicaciones={() => setShowUbicaciones((v) => !v)}
        layerLoading={layerLoading}
      />) : null}

      {cmMapScope && portalQuery && !gateOpen ? (
        <MapCatalogPanel key={portalQuery.slug}
          open={panelOpen} onOpen={() => { setPanelOpen(true); if (!window.matchMedia("(min-width: 1024px)").matches) setSelectedPortalProject(null); setSelectedLicense(null); }} onClose={() => setPanelOpen(false)}
          municipality={portalQuery.nombre} onChangeMunicipality={() => setGateOpen(true)}
          items={catalogFiltered.map(({ item }) => item)} selectedId={selectedPortalItem?.id || licenseItem?.id}
          onSelect={(id) => { const entry = catalogProjects.find(({ project }) => project.id === id); if (entry) { setShowSigma(true); onSelectPortalProject(entry.project); } }}
          query={catalogQuery} onQuery={setCatalogQuery} category={catalogCategory} onCategory={setCatalogCategory} categories={catalogCategory && !catalogCategories.includes(catalogCategory) ? [catalogCategory, ...catalogCategories] : catalogCategories}
          totalLoaded={catalogProjects.length - otherProjects.length} meta={portalMapMeta} loading={portalLoading} error={portalErr}
          showLayerControls={portalQuery.slug === "madrid"}
          showProjects={showSigma} onToggleProjects={() => setShowSigma(v => !v)}
          showLicenses={showUbicaciones} onToggleLicenses={() => setShowUbicaciones(v => !v)}
          from={dateFrom} to={dateTo} onFrom={setDateFrom} onTo={setDateTo}
          others={otherProjects}
          licenseControls={<>{showUbicaciones ? (
            <fieldset className="space-y-2 border-t border-slate-100 pt-3">
              <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Qué se va a hacer
              </legend>
              <p className="text-xs leading-relaxed text-slate-500">
                Según la última licencia del edificio (objeto, uso, tipo y procedimiento). Desmarca
                las que no quieras ver.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setActuacionQueEnabled(allActuacionQueEnabled())}
                  className="text-xs font-medium text-[var(--portal-accent)] hover:underline"
                >
                  Todas
                </button>
                <button
                  type="button"
                  onClick={() => setActuacionQueEnabled(new Set())}
                  className="text-xs font-medium text-slate-500 hover:underline"
                >
                  Ninguna
                </button>
              </div>
              <div className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
                {ACTUACION_QUE_FILTRABLES.map((codigo) => {
                  const cfg = getActuacionQueMapStyle(codigo);
                  const on = actuacionQueEnabled.has(codigo);
                  return (
                    <label
                      key={codigo}
                      className="flex cursor-pointer items-center gap-2 text-xs text-slate-700"
                    >
                      <input
                        type="checkbox"
                        className="accent-[var(--portal-accent)]"
                        checked={on}
                        onChange={() => toggleActuacionQue(codigo)}
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
          ) : null}</>}
        />
      ) : null}

      {cmMapScope ? (
        <MapMunicipioGate
          open={gateOpen}
          onCancel={portalQuery ? () => setGateOpen(false) : undefined}
          initialSlug={portalQuery?.slug}
          initialFrom={portalQuery?.from}
          initialTo={portalQuery?.to}
          onConfirm={selectMunicipio}
        />
      ) : null}

      {!cmMapScope && !panelOpen && !gateOpen ? (
        <button
          type="button"
          onClick={() => setPanelOpen(true)}
          className="absolute bottom-5 right-5 z-[1100] rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-800 shadow-lg md:bg-white/95 md:backdrop-blur-sm sm:bottom-auto sm:right-auto sm:left-4 sm:top-4"
        >
          Filtros
        </button>
      ) : null}

      {!cmMapScope && panelOpen ? (
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
            <h2 className="text-lg font-bold tracking-tight text-slate-900">
              {cmMapScope ? portalQuery?.nombre ?? "Elige un municipio" : "Madrid"}
            </h2>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-600">
              {cmMapScope
                ? portalMapMeta
                  ? `${(portalMapMeta.proyectosEnRango ?? 0).toLocaleString("es-ES")} proyectos${
                      dateFrom || dateTo ? " con actividad en estas fechas" : ""
                    }${
                      portalHasPolygons
                        ? ` · ${(portalMapMeta.proyectosPoligonos ?? 0).toLocaleString("es-ES")} con parcela en el mapa.`
                        : ` · ${(portalMapMeta.proyectosAprox ?? 0).toLocaleString("es-ES")} sin coordenada exacta, en banderas.`
                    }`
                  : "Elige un municipio. La fecha es un filtro opcional."
                : "Activa capas arriba del mapa. Busca aquí; pulsa un ámbito de planeamiento para ver qué implica."}
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
                Qué se va a hacer
              </legend>
              <p className="text-xs leading-relaxed text-slate-500">
                Según la última licencia del edificio (objeto, uso, tipo y procedimiento). Desmarca
                las que no quieras ver.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setActuacionQueEnabled(allActuacionQueEnabled())}
                  className="text-xs font-medium text-[var(--portal-accent)] hover:underline"
                >
                  Todas
                </button>
                <button
                  type="button"
                  onClick={() => setActuacionQueEnabled(new Set())}
                  className="text-xs font-medium text-slate-500 hover:underline"
                >
                  Ninguna
                </button>
              </div>
              <div className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
                {ACTUACION_QUE_FILTRABLES.map((codigo) => {
                  const cfg = getActuacionQueMapStyle(codigo);
                  const on = actuacionQueEnabled.has(codigo);
                  return (
                    <label
                      key={codigo}
                      className="flex cursor-pointer items-center gap-2 text-xs text-slate-700"
                    >
                      <input
                        type="checkbox"
                        className="accent-[var(--portal-accent)]"
                        checked={on}
                        onChange={() => toggleActuacionQue(codigo)}
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
              Última actividad
            </legend>
            <p className="text-xs leading-relaxed text-slate-500">
              {cmMapScope
                ? "Opcional. Es el último movimiento que tenemos, no el día en que empezó el expediente. Si lo dejas vacío, se ve el municipio entero."
                : "Última licencia del edificio o última actividad del proyecto. Sin fecha no aparece si filtras."}
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
            {dateFrom && dateTo && dateFrom > dateTo ? (
              <p className="text-xs text-amber-800">La fecha inicial tiene que ser anterior a la final.</p>
            ) : null}
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
            <>
              <fieldset className="space-y-2 border-t border-slate-100 pt-3">
                <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Proyectos
                </legend>
                <label className="block space-y-1">
                  <span className="text-xs text-slate-600">Vista en mapa</span>
                  <select
                    id="sigma-map-mode"
                    value={mapMode}
                    onChange={(e) => setMapMode(e.target.value as SigmaMapMode)}
                    className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm text-slate-800 outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/20"
                  >
                    {SIGMA_MAP_MODES.map(({ id, label }) => (
                      <option key={id} value={id}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
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

              {clasificacionAxisMeta && clasificacionFilters ? (
                <SigmaClassificationFilterPanel
                  meta={clasificacionAxisMeta}
                  filters={clasificacionFilters}
                  onChange={setClasificacionFilters}
                />
              ) : layerLoading ? (
                <p className="border-t border-slate-100 pt-3 text-xs text-slate-400">
                  Cargando clasificación…
                </p>
              ) : null}
            </>
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
