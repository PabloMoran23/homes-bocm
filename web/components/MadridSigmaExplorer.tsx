"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { normSearch } from "@/lib/madrid";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import {
  expedienteAnioCodigo,
  SIGMA_DEFAULT_MIN_YEAR_EXCLUSIVE_2020,
  sigmaActivityMs,
  sigmaPassesMinYearInclusive,
  sigmaPassesPortalLink,
} from "@/lib/madrid-sigma-filters";
import { projectPath } from "@/lib/project-display";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import { SIGMA_MAP_LEGEND } from "@/lib/map-sigma-colors";
import { filterSigmaMapFeaturesByBBox, SIGMA_MAP_DEFAULT_MAX_BBOX_KM2 } from "@/lib/sigma-map-geometry";
import type { SigmaBocmPopupLink, SectorFeatureCollection } from "@/lib/sector-geo";
import type { MadridSigmaDataset, SigmaExpediente } from "@/lib/types";

type MadridSigmaBocmProjectsFile = {
  generatedAt?: string | null;
  expedienteKeys?: number;
  byExpediente?: Record<string, SigmaBocmPopupLink[]>;
};

type SigmaMapMode = "ip" | "ad" | "gestion" | "urbanizacion";

type SigmaSourceFilter =
  | ""
  | "informacion_publica"
  | "tramitados_ad"
  | "tramitados_gestion"
  | "tramitados_urbanizacion";

const SIGMA_LAYER_URL: Record<Exclude<SigmaMapMode, "ip">, string> = {
  ad: "/data/madrid-sigma-ad.geojson",
  gestion: "/data/madrid-sigma-gestion.geojson",
  urbanizacion: "/data/madrid-sigma-urbanizacion.geojson",
};

const ProjectsMap = dynamic(
  () => import("./ProjectsMap").then((m) => ({ default: m.ProjectsMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[min(36vh,380px)] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
        Cargando mapa…
      </div>
    ),
  },
);

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{value}</p>
    </div>
  );
}

export function MadridSigmaExplorer() {
  const [data, setData] = useState<MadridSigmaDataset | null>(null);
  const [ipGeo, setIpGeo] = useState<SectorFeatureCollection | null>(null);
  const [geoCache, setGeoCache] = useState<Partial<Record<SigmaMapMode, SectorFeatureCollection>>>({});
  const [bocmByExpediente, setBocmByExpediente] = useState<Record<string, SigmaBocmPopupLink[]> | null>(null);
  const [mapMode, setMapMode] = useState<SigmaMapMode>("ip");
  const [layerLoading, setLayerLoading] = useState(false);
  const [layerErr, setLayerErr] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [source, setSource] = useState<SigmaSourceFilter>("");
  const [fase, setFase] = useState("");
  /** Polígonos con bbox enorme (PGOUM, catálogo global…) tap el resto; mostrar opcionalmente. */
  const [showHugeSigmaPolygons, setShowHugeSigmaPolygons] = useState(false);
  const [sigmaMapOnlyWithPortal, setSigmaMapOnlyWithPortal] = useState(false);
  const [sigmaMinYearInclusive, setSigmaMinYearInclusive] = useState<number | null>(
    SIGMA_DEFAULT_MIN_YEAR_EXCLUSIVE_2020,
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [sigmaRes, geoRes] = await Promise.all([
          fetch("/data/madrid-sigma.json"),
          fetch("/data/madrid-sigma-ip.geojson"),
        ]);
        if (!sigmaRes.ok) throw new Error(String(sigmaRes.status));
        const json = (await sigmaRes.json()) as MadridSigmaDataset;
        if (!cancelled) setData(json);
        if (geoRes.ok && !cancelled) {
          const fc = (await geoRes.json()) as SectorFeatureCollection;
          setIpGeo(fc);
          setGeoCache((prev) => ({ ...prev, ip: fc }));
        }
      } catch {
        if (!cancelled) {
          setErr(
            "No se pudieron cargar los proyectos de planeamiento. Ejecuta: python3 -m sector_geometry.madrid_ayto_sync && npm run build-data",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/data/madrid-sigma-bocm-projects.json");
        if (!res.ok) return;
        const json = (await res.json()) as MadridSigmaBocmProjectsFile;
        if (!cancelled && json.byExpediente && typeof json.byExpediente === "object") {
          setBocmByExpediente(json.byExpediente);
        }
      } catch {
        /* opcional: índice no generado */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const anosSigmaCatalog = useMemo(() => {
    if (!data?.expedientes?.length) return [];
    const ys = new Set<number>();
    for (const e of data.expedientes) {
      const row = e as unknown as Record<string, unknown>;
      const ms = sigmaActivityMs(row);
      if (ms != null) ys.add(new Date(ms).getUTCFullYear());
      else {
        const yy = expedienteAnioCodigo(e.EXP_TX_NUMERO ?? "");
        if (yy != null) ys.add(yy);
      }
    }
    return [...ys].sort((a, b) => b - a);
  }, [data]);

  useEffect(() => {
    if (!anosSigmaCatalog.length) return;
    setSigmaMinYearInclusive((prev) => {
      if (prev === null) return null;
      if (anosSigmaCatalog.includes(prev)) return prev;
      const post = anosSigmaCatalog.filter((y) => y >= SIGMA_DEFAULT_MIN_YEAR_EXCLUSIVE_2020);
      if (post.length) return Math.min(...post);
      return anosSigmaCatalog[anosSigmaCatalog.length - 1]!;
    });
  }, [anosSigmaCatalog]);

  const sigmaPopupOptions = useMemo(() => {
    if (!bocmByExpediente || Object.keys(bocmByExpediente).length === 0) return null;
    return { sigmaBocmByExpediente: bocmByExpediente };
  }, [bocmByExpediente]);

  const fases = useMemo(() => {
    if (!data) return [];
    const s = new Set<string>();
    for (const e of data.expedientes) {
      const f = (e.FAS_TX_DENOM || "").trim();
      if (f) s.add(f);
    }
    return [...s].sort((a, b) => a.localeCompare(b, "es"));
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const nq = normSearch(q.trim());
    return data.expedientes.filter((e) => {
      if (source && e.source !== source) return false;
      if (fase && (e.FAS_TX_DENOM || "") !== fase) return false;
      if (!nq) {
        /* search vacío: sigue */
      } else {
        const hay =
          normSearch(e.EXP_TX_NUMERO || "").includes(nq) ||
          normSearch(e.EXP_TX_DENOM || "").includes(nq) ||
          normSearch(e.FIG_TX_ETIQ || "").includes(nq) ||
          normSearch(e.FAS_TX_DENOM || "").includes(nq);
        if (!hay) return false;
      }

      const row = e as unknown as Record<string, unknown>;
      if (sigmaMapOnlyWithPortal && bocmByExpediente && !sigmaPassesPortalLink(row, bocmByExpediente)) {
        return false;
      }
      if (
        sigmaMinYearInclusive != null &&
        !sigmaPassesMinYearInclusive(
          {
            EXP_TX_NUMERO: e.EXP_TX_NUMERO,
            FEX_DT_APROB: row.FEX_DT_APROB,
            FEX_DT_INFOPUB_INI: row.FEX_DT_INFOPUB_INI,
            FEX_DT_INFOPUB_FIN: row.FEX_DT_INFOPUB_FIN,
          },
          sigmaMinYearInclusive,
        )
      ) {
        return false;
      }
      return true;
    });
  }, [data, q, source, fase, sigmaMapOnlyWithPortal, bocmByExpediente, sigmaMinYearInclusive]);

  const ipGeoFiltered = useMemo(() => {
    if (!ipGeo?.features?.length) return null;
    const nq = normSearch(q.trim());
    if (!nq) return ipGeo;
    return {
      type: "FeatureCollection" as const,
      features: ipGeo.features.filter((f) => {
        const p = (f.properties || {}) as Record<string, unknown>;
        return (
          normSearch(String(p.EXP_TX_DENOM || "")).includes(nq) ||
          normSearch(String(p.EXP_TX_NUMERO || "")).includes(nq)
        );
      }),
    };
  }, [ipGeo, q]);

  const polygonGeo = mapMode === "ip" ? ipGeo : geoCache[mapMode] ?? null;

  const polygonGeoFiltered = useMemo(() => {
    if (!polygonGeo?.features?.length) return null;
    const nq = normSearch(q.trim());
    if (!nq) return polygonGeo;
    return {
      type: "FeatureCollection" as const,
      features: polygonGeo.features.filter((f) => {
        const p = (f.properties || {}) as Record<string, unknown>;
        return (
          normSearch(String(p.EXP_TX_DENOM || "")).includes(nq) ||
          normSearch(String(p.EXP_TX_NUMERO || "")).includes(nq) ||
          normSearch(String(p.FIG_TX_ETIQ || "")).includes(nq)
        );
      }),
    };
  }, [polygonGeo, q]);

  const ipGeoSemanticFiltered = useMemo(() => {
    if (!ipGeoFiltered?.features?.length) return null;
    let feats = ipGeoFiltered.features;
    if (sigmaMapOnlyWithPortal && bocmByExpediente) {
      feats = feats.filter((f) =>
        sigmaPassesPortalLink((f.properties || {}) as Record<string, unknown>, bocmByExpediente),
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
    if (feats.length === ipGeoFiltered.features.length) return ipGeoFiltered;
    return { type: "FeatureCollection" as const, features: feats };
  }, [ipGeoFiltered, sigmaMapOnlyWithPortal, bocmByExpediente, sigmaMinYearInclusive]);

  const polygonGeoSemanticFiltered = useMemo(() => {
    if (!polygonGeoFiltered?.features?.length) return null;
    let feats = polygonGeoFiltered.features;
    if (sigmaMapOnlyWithPortal && bocmByExpediente) {
      feats = feats.filter((f) =>
        sigmaPassesPortalLink((f.properties || {}) as Record<string, unknown>, bocmByExpediente),
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
    if (feats.length === polygonGeoFiltered.features.length) return polygonGeoFiltered;
    return { type: "FeatureCollection" as const, features: feats };
  }, [polygonGeoFiltered, sigmaMapOnlyWithPortal, bocmByExpediente, sigmaMinYearInclusive]);

  const { polygonGeoForMap, polygonExcludedHuge } = useMemo(() => {
    if (!polygonGeoSemanticFiltered?.features?.length)
      return { polygonGeoForMap: null as SectorFeatureCollection | null, polygonExcludedHuge: 0 };
    if (showHugeSigmaPolygons)
      return { polygonGeoForMap: polygonGeoSemanticFiltered, polygonExcludedHuge: 0 };
    const { visible, excluded } = filterSigmaMapFeaturesByBBox(
      polygonGeoSemanticFiltered,
      SIGMA_MAP_DEFAULT_MAX_BBOX_KM2,
    );
    return { polygonGeoForMap: visible, polygonExcludedHuge: excluded };
  }, [polygonGeoSemanticFiltered, showHugeSigmaPolygons]);

  useEffect(() => {
    if (mapMode === "ip" || geoCache[mapMode]) return;
    const ac = new AbortController();
    setLayerLoading(true);
    setLayerErr(null);
    (async () => {
      try {
        const url = SIGMA_LAYER_URL[mapMode];
        const geoRes = await fetch(url, { signal: ac.signal });
        if (!geoRes.ok) {
          throw new Error(
            geoRes.status === 404
              ? `Falta ${url.replace("/data/", "")} · ejecuta madrid_ayto_sync && npm run build-data`
              : String(geoRes.status),
          );
        }
        const fc = (await geoRes.json()) as SectorFeatureCollection;
        if (!ac.signal.aborted) setGeoCache((prev) => ({ ...prev, [mapMode]: fc }));
      } catch (e) {
        if (ac.signal.aborted) return;
        setLayerErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!ac.signal.aborted) setLayerLoading(false);
      }
    })();
    return () => ac.abort();
  }, [mapMode, geoCache]);

  if (err) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {err}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-200" />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-xl bg-slate-200" />
      </div>
    );
  }

  const c = data.counts;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Total proyectos" value={(c?.total ?? data.expedientes.length).toLocaleString("es-ES")} />
        <Stat label="Únicos" value={c?.expedientes_unicos?.toLocaleString("es-ES") ?? "—"} />
        <Stat label="Información pública" value={c?.informacion_publica ?? "—"} />
        <Stat label="Planeamiento AD" value={c?.tramitados_ad ?? "—"} />
        <Stat label="Gestión" value={c?.tramitados_gestion ?? "—"} />
        <Stat label="Urbanización" value={c?.tramitados_urbanizacion ?? "—"} />
      </div>

      <p className="text-xs text-slate-500">
        Sincronizado: {data.generatedAt ? new Date(data.generatedAt).toLocaleString("es-ES") : "—"}
        {data.note ? ` · ${data.note}` : null}
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[200px] flex-1 space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Buscar</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Expediente, denominación, figura…"
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          />
        </label>
        <label className="min-w-[140px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Origen</span>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value as typeof source)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)]"
          >
            <option value="">Todos</option>
            <option value="informacion_publica">Información pública</option>
            <option value="tramitados_ad">Planeamiento AD</option>
            <option value="tramitados_gestion">Gestión</option>
            <option value="tramitados_urbanizacion">Urbanización</option>
          </select>
        </label>
        <label className="min-w-[160px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Fase</span>
          <select
            value={fase}
            onChange={(e) => setFase(e.target.value)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)]"
          >
            <option value="">Todas</option>
            {fases.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
      </div>

      <p className="text-sm text-slate-600">
        <span className="font-semibold text-slate-900">{filtered.length.toLocaleString("es-ES")}</span>{" "}
        expedientes
        {filtered.length !== data.expedientes.length ? (
          <span className="text-slate-500">
            {" "}
            de {data.expedientes.length.toLocaleString("es-ES")}
          </span>
        ) : null}
        <span className="mt-1 block text-xs text-slate-500">
          Listado y mapa comparten el filtro de portal y el umbral de año; el desplegable muestra{" "}
          <strong>todos los años</strong> detectados en el catálogo municipal (fechas de servicio o año del
          expediente). Por defecto: desde {SIGMA_DEFAULT_MIN_YEAR_EXCLUSIVE_2020}{" "}
          <span className="whitespace-nowrap">(posterior al calendario 2020)</span>.
        </span>
      </p>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-800">Mapa de proyectos</h2>
        <p className="mb-3 text-xs text-slate-600">
          Haz clic en un polígono: <strong>ficha del proyecto</strong> para todos; enlace{" "}
          <strong>BOCM</strong> si hay anuncio parseado. Índice regenerado con{" "}
          <code className="rounded bg-slate-100 px-1 text-[11px]">npm run build-data</code>.
        </p>
        <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="sigma-map-layer"
              className="accent-[var(--portal-accent)]"
              checked={mapMode === "ip"}
              onChange={() => setMapMode("ip")}
            />
            Información pública ({ipGeo?.features?.length ?? 0})
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="sigma-map-layer"
              className="accent-[var(--portal-accent)]"
              checked={mapMode === "ad"}
              onChange={() => setMapMode("ad")}
            />
            Planeamiento AD ({c?.tramitados_ad?.toLocaleString("es-ES") ?? "—"})
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="sigma-map-layer"
              className="accent-[var(--portal-accent)]"
              checked={mapMode === "gestion"}
              onChange={() => setMapMode("gestion")}
            />
            Gestión ({c?.tramitados_gestion?.toLocaleString("es-ES") ?? "—"})
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="sigma-map-layer"
              className="accent-[var(--portal-accent)]"
              checked={mapMode === "urbanizacion"}
              onChange={() => setMapMode("urbanizacion")}
            />
            Urbanización ({c?.tramitados_urbanizacion?.toLocaleString("es-ES") ?? "—"})
          </label>
          <label className="inline-flex cursor-pointer items-center gap-2 text-slate-600">
            <input
              type="checkbox"
              className="accent-[var(--portal-accent)]"
              checked={showHugeSigmaPolygons}
              onChange={(e) => setShowHugeSigmaPolygons(e.target.checked)}
            />
            Mostrar polígonos muy extensos (&gt;{SIGMA_MAP_DEFAULT_MAX_BBOX_KM2} km² aprox.)
          </label>
        </div>
        <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-100 pt-3 text-sm">
          <label className="inline-flex cursor-pointer items-center gap-2 text-slate-700">
            <input
              type="checkbox"
              className="accent-[var(--portal-accent)]"
              checked={sigmaMapOnlyWithPortal}
              onChange={(e) => setSigmaMapOnlyWithPortal(e.target.checked)}
            />
            Solo con anuncio BOCM en portal
          </label>
          <label className="flex flex-wrap items-center gap-1.5 text-slate-700">
            <span className="text-[10px] font-medium uppercase tracking-wide text-slate-500 whitespace-nowrap">
              Año mín.
            </span>
            <select
              title="Incluir proyectos con actividad desde 1 ene de este año o con nº de expediente de ese año"
              value={sigmaMinYearInclusive === null ? "" : String(sigmaMinYearInclusive)}
              onChange={(e) => {
                const raw = e.target.value;
                setSigmaMinYearInclusive(raw === "" ? null : Number(raw));
              }}
              className="h-7 max-w-[5rem] shrink-0 rounded border border-slate-200 bg-white px-1 py-0 text-[11px] leading-tight outline-none focus:border-[var(--portal-accent)]"
            >
              <option value="">Todos</option>
              {anosSigmaCatalog.map((y) => (
                <option key={y} value={String(y)}>
                  {y}
                </option>
              ))}
            </select>
            <span className="text-[10px] text-slate-400">({anosSigmaCatalog.length} años)</span>
          </label>
        </div>

        {mapMode !== "ip" && layerLoading ? (
          <div className="flex h-[min(40vh,440px)] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-600">
            Cargando polígonos…
          </div>
        ) : null}
        {layerErr ? (
          <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {layerErr}
          </div>
        ) : null}
        {!layerLoading && !layerErr && polygonGeoForMap && polygonGeoForMap.features.length > 0 ? (
          <>
            <ProjectsMap
              points={[]}
              sectorGeoJson={polygonGeoForMap}
              dataScope="full"
              variant="detail"
              sectorCountLabel={
                mapMode === "ip"
                  ? "en información pública"
                  : mapMode === "ad"
                    ? "planeamiento AD"
                    : mapMode === "gestion"
                      ? "gestión"
                      : "urbanización"
              }
              heightClassName="h-[min(40vh,440px)]"
              sigmaPopupOptions={sigmaPopupOptions}
            />
            <p className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
              {polygonExcludedHuge > 0 ? (
                <span>
                  Ocultos {polygonExcludedHuge} muy extensos (activa «Mostrar polígonos muy extensos»).
                </span>
              ) : null}
              {mapMode === "ip" ? (
                <span>
                  La capa «información pública» solo incluye expedientes en ese trámite en este momento.
                </span>
              ) : null}
              <span className="inline-flex items-center gap-1">
                <span className={`inline-block ${SIGMA_MAP_LEGEND.planeamiento}`} />
                Planeamiento
              </span>
              <span className="inline-flex items-center gap-1">
                <span className={`inline-block ${SIGMA_MAP_LEGEND.gestion}`} />
                Gestión
              </span>
              <span className="inline-flex items-center gap-1">
                <span className={`inline-block ${SIGMA_MAP_LEGEND.urbanizacion}`} />
                Urbanización
              </span>
            </p>
          </>
        ) : null}
        {!layerLoading && !layerErr && (!polygonGeoForMap || polygonGeoForMap.features.length === 0) ? (
          <p className="text-sm text-slate-500">
            {polygonGeoFiltered && polygonGeoFiltered.features.length === 0 && q.trim()
              ? "Ningún expediente coincide con la búsqueda."
              : polygonGeoSemanticFiltered?.features?.length === 0
                ? "Ningún polígono cumple el filtro de portal y/o el umbral de año."
                : polygonGeoSemanticFiltered &&
                    polygonGeoSemanticFiltered.features.length > 0 &&
                    polygonExcludedHuge > 0 &&
                    !showHugeSigmaPolygons
                  ? "Todos los polígonos superan el umbral de tamaño; activa «Mostrar polígonos muy extensos»."
                  : mapMode === "ip"
                    ? "Sin geometría de información pública disponible."
                    : "Sin polígonos en esta capa o aún no cargada."}
          </p>
        ) : null}
      </div>

      <div className="overflow-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[800px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Expediente</th>
              <th className="px-3 py-2">Denominación</th>
              <th className="px-3 py-2">Fase</th>
              <th className="px-3 py-2">Figura</th>
              <th className="px-3 py-2">Origen</th>
              <th className="px-3 py-2 text-right whitespace-nowrap min-w-[8rem]">Enlaces</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.slice(0, 500).map((e) => (
              <SigmaRow key={`${e.source}-${e.EXP_TX_NUMERO}`} e={e} bocmByExpediente={bocmByExpediente} />
            ))}
          </tbody>
        </table>
        {filtered.length > 500 ? (
          <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
            Mostrando 500 de {filtered.length.toLocaleString("es-ES")}. Afina la búsqueda.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function SigmaRow({
  e,
  bocmByExpediente,
}: {
  e: SigmaExpediente;
  bocmByExpediente: Record<string, SigmaBocmPopupLink[]> | null;
}) {
  const src =
    e.source === "informacion_publica"
      ? "IP"
      : e.source === "tramitados_ad"
        ? "AD"
        : e.source === "tramitados_gestion"
          ? "GES"
          : e.source === "tramitados_urbanizacion"
            ? "URB"
            : e.source;
  const g = e.EXP_TX_NUMERO ? expedienteGrupoKeyFromVariant(String(e.EXP_TX_NUMERO)) : "";
  const bocmHits = g && bocmByExpediente ? bocmByExpediente[g] : undefined;
  return (
    <tr className="hover:bg-slate-50">
      <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-slate-800">
        {e.EXP_TX_NUMERO || "—"}
      </td>
      <td className="max-w-md px-3 py-2 text-slate-800">{e.EXP_TX_DENOM || "—"}</td>
      <td className="px-3 py-2 text-slate-600">{e.FAS_TX_DENOM || "—"}</td>
      <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-slate-500">
        {e.FIG_TX_ETIQ || "—"}
      </td>
      <td className="px-3 py-2">
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-medium ${
            e.source === "informacion_publica"
              ? "bg-sky-100 text-sky-800"
              : e.source === "tramitados_gestion"
                ? "bg-violet-100 text-violet-900"
                : e.source === "tramitados_urbanizacion"
                  ? "bg-amber-100 text-amber-900"
                  : "bg-slate-100 text-slate-700"
          }`}
        >
          {src}
        </span>
      </td>
      <td className="px-3 py-2 text-right whitespace-nowrap">
        {g ? (
          <Link
            href={sigmaFichaPath(g)}
            className="mr-3 text-xs font-semibold text-[var(--portal-accent)] hover:underline"
            prefetch={false}
          >
            Ficha
          </Link>
        ) : null}
        {bocmHits?.length ? (
          <Link
            href={projectPath(bocmHits[0].id)}
            className="mr-3 text-xs font-semibold text-teal-700 hover:underline"
            prefetch={false}
            title="Anuncio BOCM enlazado"
          >
            BOCM
          </Link>
        ) : null}
        {e.Enlace ? (
          <a
            href={e.Enlace}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-slate-500 hover:underline"
          >
            Ayuntamiento ↗
          </a>
        ) : null}
      </td>
    </tr>
  );
}
