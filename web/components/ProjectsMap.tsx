"use client";

import { Fragment, useCallback, useEffect, useMemo } from "react";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  ScaleControl,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { collectMapBounds } from "@/lib/map-bounds";
import { SectorFeaturesGeoLayer } from "@/components/map/SectorFeaturesGeoLayer";
import type { FeaturePopupOptions, SectorFeatureCollection } from "@/lib/sector-geo";
import { HOMES_MAP_TILE_URL } from "@/lib/map-tiles";

export type MapPoint = {
  municipio: string;
  count: number;
  lat: number;
  lng: number;
};

const MADRID_CENTER: LatLngExpression = [40.42, -3.703];
const DEFAULT_ZOOM = 9;

const detailPinIcon = L.divIcon({
  className: "",
  html: `<span style="display:block;width:28px;height:28px;margin:-28px 0 0 -14px;background:#0f766e;border:3px solid #fff;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 2px 8px rgba(15,118,110,0.45)"></span>`,
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

function radiusForCount(n: number) {
  return Math.min(10 + Math.sqrt(n) * 2.4, 36);
}

function detailFitOptions(
  points: MapPoint[],
  sectorGeoJson?: SectorFeatureCollection | null,
): { padding: [number, number]; maxZoom: number } {
  const nSectors = sectorGeoJson?.features?.length ?? 0;
  const nPoints = points.length;
  if (nSectors >= 1 && nPoints === 0) {
    return {
      padding: nSectors === 1 ? [24, 24] : [36, 36],
      maxZoom: nSectors === 1 ? 18 : 15,
    };
  }
  if (nSectors <= 1 && nPoints <= 1) {
    return { padding: [32, 32], maxZoom: 17 };
  }
  return { padding: [40, 40], maxZoom: 14 };
}

function FitBounds({
  points,
  sectorGeoJson,
  variant,
}: {
  points: MapPoint[];
  sectorGeoJson?: SectorFeatureCollection | null;
  variant: "explore" | "detail";
}) {
  const map = useMap();
  const sectorKey = sectorGeoJson?.features?.length ?? 0;

  const fit = useCallback(() => {
    const bounds = collectMapBounds(points, sectorGeoJson);
    if (!bounds) return;

    if (variant === "detail") {
      const { padding, maxZoom } = detailFitOptions(points, sectorGeoJson);
      map.fitBounds(bounds, { padding, maxZoom, animate: false });
      return;
    }

    if (points.length === 1 && !(sectorGeoJson?.features?.length)) {
      const p = points[0];
      map.setView([p.lat, p.lng], 11, { animate: false });
      return;
    }

    map.fitBounds(bounds, {
      padding: [52, 52],
      maxZoom: 11,
      animate: false,
    });
  }, [map, points, sectorGeoJson, variant]);

  useEffect(() => {
    fit();
    const t = window.setTimeout(fit, 150);
    const t2 = window.setTimeout(fit, 450);
    return () => {
      window.clearTimeout(t);
      window.clearTimeout(t2);
    };
  }, [fit, sectorKey]);

  return null;
}

function MapResizeFix({
  points,
  sectorGeoJson,
  variant,
}: {
  points: MapPoint[];
  sectorGeoJson?: SectorFeatureCollection | null;
  variant: "explore" | "detail";
}) {
  const map = useMap();
  const sectorKey = sectorGeoJson?.features?.length ?? 0;

  const fit = useCallback(() => {
    const bounds = collectMapBounds(points, sectorGeoJson);
    if (!bounds) return;
    if (variant === "detail") {
      const { padding, maxZoom } = detailFitOptions(points, sectorGeoJson);
      map.fitBounds(bounds, { padding, maxZoom, animate: false });
    } else if (points.length === 1 && !(sectorGeoJson?.features?.length)) {
      map.setView([points[0].lat, points[0].lng], 11, { animate: false });
    } else {
      map.fitBounds(bounds, { padding: [52, 52], maxZoom: 11, animate: false });
    }
  }, [map, points, sectorGeoJson, variant]);

  useEffect(() => {
    const run = () => {
      map.invalidateSize({ pan: false });
      fit();
    };
    const t = window.setTimeout(run, 100);
    const t2 = window.setTimeout(run, 400);
    const el = map.getContainer();
    const ro =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            window.requestAnimationFrame(run);
          })
        : null;
    ro?.observe(el);
    return () => {
      window.clearTimeout(t);
      window.clearTimeout(t2);
      ro?.disconnect();
    };
  }, [map, fit, sectorKey]);

  return null;
}

export type ProjectsMapDataScope = "filtered" | "full";

export function ProjectsMap({
  points,
  sectorGeoJson = null,
  dataScope = "filtered",
  variant = "explore",
  heightClassName = "h-[min(56vh,580px)]",
  sectorCountLabel = "sectores",
  sigmaPopupOptions = null,
}: {
  points: MapPoint[];
  sectorGeoJson?: SectorFeatureCollection | null;
  dataScope?: ProjectsMapDataScope;
  variant?: "explore" | "detail";
  heightClassName?: string;
  /** Etiqueta en cabecera del mapa (p. ej. «expedientes IP»). */
  sectorCountLabel?: string;
  sigmaPopupOptions?: FeaturePopupOptions | null;
}) {
  const nMunicipios = points.length;
  const totalAnuncios = points.reduce((acc, p) => acc + p.count, 0);
  const nSectors = sectorGeoJson?.features?.length ?? 0;
  const isFullDataset = dataScope === "full";
  const isDetail = variant === "detail";
  const hasMapContent = nMunicipios > 0 || nSectors > 0;

  const sectorLayerKey = `sectors-${nSectors}-${dataScope}-${variant}`;

  return (
    <div className="homes-map-shell group relative">
      <div
        className="pointer-events-none absolute inset-0 z-[500] rounded-2xl ring-1 ring-black/[0.06] ring-inset"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 z-[500] rounded-2xl shadow-[inset_0_1px_0_0_rgba(255,255,255,0.65)]"
        aria-hidden
      />

      <div className="relative overflow-hidden rounded-2xl border border-teal-100/80 bg-gradient-to-b from-white to-teal-50/45 shadow-[0_1px_0_rgba(255,255,255,0.95)_inset,0_24px_60px_-26px_rgba(15,118,110,0.35)]">
        {!isDetail ? (
          <div className="pointer-events-none absolute left-0 right-0 top-0 z-[1000] flex items-start justify-between gap-3 p-3 sm:p-4">
            <div className="pointer-events-auto flex max-w-[min(100%,20rem)] flex-col gap-1 rounded-xl border border-white/80 bg-white/90 px-3 py-2 shadow-md shadow-slate-900/5 backdrop-blur-md sm:max-w-none sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-2.5">
              <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--portal-accent)]">
                Homes
              </span>
              <span className="hidden h-4 w-px bg-slate-200 sm:block" aria-hidden />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">Mapa de actividad</p>
                <p className="text-xs text-slate-500">
                  {nMunicipios > 0 || nSectors > 0 ? (
                    <>
                      {nMunicipios > 0 ? (
                        <>
                          <span className="font-medium text-slate-700">{nMunicipios}</span> municipios
                          <span className="mx-1.5 text-slate-300">·</span>
                          <span className="font-medium text-slate-700">
                            {totalAnuncios.toLocaleString("es-ES")}
                          </span>{" "}
                          {isFullDataset ? "anuncios" : "anuncios (filtro)"}
                        </>
                      ) : null}
                      {nSectors > 0 ? (
                        <>
                          {nMunicipios > 0 ? <span className="mx-1.5 text-slate-300">·</span> : null}
                          <span className="font-medium text-slate-700">{nSectors}</span> {sectorCountLabel}
                        </>
                      ) : null}
                    </>
                  ) : (
                    "Esperando datos…"
                  )}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <div className={`relative w-full ${heightClassName}`}>
          {!hasMapContent ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 bg-gradient-to-b from-slate-50 to-white px-6 text-center">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--portal-accent-soft)] bg-[var(--portal-accent-soft)]/40 shadow-inner"
                aria-hidden
              >
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="text-[var(--portal-accent)]">
                  <path
                    fill="currentColor"
                    fillOpacity="0.2"
                    d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 11.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z"
                  />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">
                  {isDetail
                    ? "Sin ubicación en el mapa"
                    : isFullDataset
                      ? "Sin mapa todavía"
                      : "Sin puntos en este filtro"}
                </p>
                <p className="mt-1 max-w-xs text-xs leading-relaxed text-slate-500">
                  {isDetail
                    ? "No hay coordenadas ni geometría de sector para este anuncio."
                    : isFullDataset
                      ? "No hay municipios con coordenadas en el índice. Ejecuta npm run build-data con geocodificación."
                      : "Ajusta municipio, territorio o búsqueda. El tamaño del círculo refleja el volumen de anuncios por municipio."}
                </p>
              </div>
            </div>
          ) : (
            <>
              <MapContainer
                center={MADRID_CENTER}
                zoom={DEFAULT_ZOOM}
                attributionControl={false}
                className="z-0 h-full w-full"
                scrollWheelZoom
                zoomControl={false}
              >
                <TileLayer attribution="" url={HOMES_MAP_TILE_URL} />
                {sectorGeoJson?.features?.length ? (
                  <SectorFeaturesGeoLayer
                    geojson={sectorGeoJson}
                    popupOptions={sigmaPopupOptions ?? undefined}
                    layerKey={sectorLayerKey}
                  />
                ) : null}
                <FitBounds points={points} sectorGeoJson={sectorGeoJson} variant={variant} />
                <MapResizeFix points={points} sectorGeoJson={sectorGeoJson} variant={variant} />
                <ZoomControl position="topright" />
                <ScaleControl position="bottomleft" imperial={false} />
                {isDetail
                  ? points.map((pt) => (
                      <Marker
                        key={`${pt.lat}-${pt.lng}`}
                        position={[pt.lat, pt.lng]}
                        icon={detailPinIcon}
                      >
                        <Popup className="homes-map-popup" closeButton minWidth={200}>
                          <p className="text-sm font-semibold text-slate-900">{pt.municipio}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {pt.lat.toFixed(5)}, {pt.lng.toFixed(5)}
                          </p>
                        </Popup>
                      </Marker>
                    ))
                  : points.map((pt) => {
                      const r = radiusForCount(pt.count);
                      return (
                        <Fragment key={pt.municipio}>
                          <CircleMarker
                            interactive={false}
                            center={[pt.lat, pt.lng]}
                            radius={r + 7}
                            pathOptions={{
                              stroke: false,
                              fillColor: "#14b8a6",
                              fillOpacity: 0.12,
                            }}
                          />
                          <CircleMarker
                            center={[pt.lat, pt.lng]}
                            radius={r}
                            pathOptions={{
                              color: "#ffffff",
                              weight: 2.5,
                              fillColor: "#0f766e",
                              fillOpacity: 0.88,
                              lineCap: "round",
                              lineJoin: "round",
                            }}
                          >
                            <Tooltip
                              direction="top"
                              offset={[0, -6]}
                              opacity={1}
                              className="!rounded-lg !border !border-slate-200/90 !bg-white/95 !px-2.5 !py-1.5 !text-xs !text-slate-800 !shadow-lg"
                            >
                              <span className="font-semibold">{pt.municipio}</span>
                              <span className="text-slate-500">
                                {" "}
                                · {pt.count} anuncio{pt.count === 1 ? "" : "s"}
                              </span>
                            </Tooltip>
                            <Popup
                              className="homes-map-popup"
                              closeButton
                              minWidth={220}
                              maxWidth={280}
                            >
                              <div className="font-sans">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--portal-accent)]">
                                  Municipio
                                </p>
                                <p className="mt-0.5 text-base font-bold leading-snug text-slate-900">
                                  {pt.municipio}
                                </p>
                                <p className="mt-3 text-sm text-slate-600">
                                  <span className="tabular-nums font-semibold text-slate-900">
                                    {pt.count.toLocaleString("es-ES")}
                                  </span>{" "}
                                  anuncio{pt.count === 1 ? "" : "s"}{" "}
                                  {isFullDataset ? "en el índice publicado." : "con el filtro actual."}
                                </p>
                                <p className="mt-2 border-t border-slate-100 pt-2 text-[11px] leading-relaxed text-slate-500">
                                  Radio aproximado al volumen. Coordenadas de referencia (centro del
                                  municipio).
                                </p>
                              </div>
                            </Popup>
                          </CircleMarker>
                        </Fragment>
                      );
                    })}
              </MapContainer>
              <div className="pointer-events-none absolute bottom-2 right-2 z-[1000] max-w-[min(100%,14rem)] text-right font-sans text-[9px] leading-tight text-slate-400/90">
                <span className="pointer-events-auto">
                  <a
                    href="https://www.openstreetmap.org/copyright"
                    className="underline decoration-slate-300/80 underline-offset-2 hover:text-slate-600"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    © OpenStreetMap
                  </a>
                  {" · "}
                  <a
                    href="https://carto.com/attributions"
                    className="underline decoration-slate-300/80 underline-offset-2 hover:text-slate-600"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    CARTO
                  </a>
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
