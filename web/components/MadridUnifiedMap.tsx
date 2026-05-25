"use client";

import { useEffect, useMemo, useRef, type ReactNode } from "react";
import {
  MapContainer,
  ScaleControl,
  TileLayer,
  ZoomControl,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { LicenciasClusterLayer } from "@/components/map/LicenciasClusterLayer";
import { SigmaPolygonsLayer } from "@/components/map/SigmaPolygonsLayer";
import type { FeaturePopupOptions, SectorFeatureCollection } from "@/lib/sector-geo";
import { LicenciaMapLegend } from "@/components/map/LicenciaMapLegend";
import { MapBoundsReporter } from "@/components/map/MapBoundsReporter";
import { MapSizeFix } from "@/components/map/MapSizeFix";
import type { MapBounds } from "@/lib/map-viewport";
import type { UbicacionesMapGeoJson } from "@/lib/madrid-ubicaciones-map";
import { SIGMA_MAP_LEGEND } from "@/lib/map-sigma-colors";
import { PROYECTOS } from "@/lib/ui-labels";
import { useLeafletMount } from "@/lib/use-leaflet-mount";
import { HOMES_MAP_TILE_URL } from "@/lib/map-tiles";

const MADRID_CENTER: LatLngExpression = [40.42, -3.703];

/** Vista por defecto al abrir /explore (ciudad entera). */
const MADRID_CITY_ZOOM = 11;
const MADRID_FIT_MAX_ZOOM = 14;
const MADRID_CITY_BOUNDS = L.latLngBounds(
  [40.348, -3.888],
  [40.502, -3.518],
);

/** Portada: zoom fijo (no fitBounds del GeoJSON completo). */
const MADRID_PREVIEW_ZOOM = 11;

/** Explorar: misma idea al entrar, sobre todo en móvil. */
const MADRID_EXPLORE_ZOOM = 12;

const MADRID_PREVIEW_BOUNDS = L.latLngBounds(
  [40.402, -3.72],
  [40.448, -3.68],
);

export type MapInitialView = "city" | "preview" | "explore";

const FIXED_VIEW_ZOOM: Partial<Record<MapInitialView, number>> = {
  preview: MADRID_PREVIEW_ZOOM,
  explore: MADRID_EXPLORE_ZOOM,
};

const FIT_PRESETS: Record<
  MapInitialView,
  { city: L.FitBoundsOptions; data: L.FitBoundsOptions; defaultZoom: number }
> = {
  city: {
    city: { padding: [28, 28], maxZoom: MADRID_CITY_ZOOM, animate: false },
    data: { padding: [48, 48], maxZoom: MADRID_FIT_MAX_ZOOM, animate: false },
    defaultZoom: MADRID_CITY_ZOOM,
  },
  preview: {
    city: { padding: [6, 6], maxZoom: MADRID_PREVIEW_ZOOM, animate: false },
    data: { padding: [8, 8], maxZoom: MADRID_PREVIEW_ZOOM, animate: false },
    defaultZoom: MADRID_PREVIEW_ZOOM,
  },
  explore: {
    city: { padding: [20, 20], maxZoom: MADRID_EXPLORE_ZOOM, animate: false },
    data: { padding: [24, 24], maxZoom: MADRID_EXPLORE_ZOOM, animate: false },
    defaultZoom: MADRID_EXPLORE_ZOOM,
  },
};

function frameMadridCity(map: L.Map, view: MapInitialView) {
  const bounds = view === "preview" ? MADRID_PREVIEW_BOUNDS : MADRID_CITY_BOUNDS;
  map.fitBounds(bounds, FIT_PRESETS[view].city);
}

/** Zoom fijo; no usar getBounds() del GeoJSON (cubre todo Madrid y aleja el mapa). */
function frameFixedZoom(map: L.Map, view: MapInitialView) {
  const zoom = FIXED_VIEW_ZOOM[view];
  if (zoom == null) return;
  map.setView(MADRID_CENTER, zoom, { animate: false });
}

function scheduleFixedZoom(map: L.Map, view: MapInitialView) {
  const apply = () => frameFixedZoom(map, view);
  apply();
  const t1 = window.setTimeout(apply, 80);
  const t2 = window.setTimeout(apply, 400);
  return () => {
    window.clearTimeout(t1);
    window.clearTimeout(t2);
  };
}

function fitLayerBounds(
  map: L.Map,
  bounds: L.LatLngBounds,
  view: MapInitialView,
  mode: "city" | "data",
) {
  if (!bounds.isValid()) return;
  map.fitBounds(bounds, FIT_PRESETS[view][mode]);
}

function UnifiedFitBounds({
  ubicaciones,
  sigma,
  fitToData = true,
  initialView = "city",
}: {
  ubicaciones: UbicacionesMapGeoJson | null;
  sigma: SectorFeatureCollection | null;
  fitToData?: boolean;
  initialView?: MapInitialView;
}) {
  const map = useMap();
  const lastFitKey = useRef("");

  useEffect(() => {
    const hasUbic = Boolean(ubicaciones?.features?.length);
    const hasSigma = Boolean(sigma?.features?.length);
    const key = `${initialView}:${fitToData}:${hasUbic ? ubicaciones!.features.length : 0}:${hasSigma ? sigma!.features.length : 0}`;

    const boundsFromLayers = (): L.LatLngBounds | null => {
      let bounds: L.LatLngBounds | null = null;
      if (hasSigma) {
        const sb = L.geoJSON(sigma as GeoJSON.FeatureCollection).getBounds();
        if (sb.isValid()) bounds = sb;
      }
      if (hasUbic) {
        const ub = L.geoJSON(ubicaciones as GeoJSON.FeatureCollection).getBounds();
        if (ub.isValid()) bounds = bounds ? bounds.extend(ub) : ub;
      }
      return bounds?.isValid() ? bounds : null;
    };

    if (!fitToData) {
      if (lastFitKey.current === key) return;
      lastFitKey.current = key;

      if (initialView === "preview" || initialView === "explore") {
        return scheduleFixedZoom(map, initialView);
      }

      const layerBounds = boundsFromLayers();
      if (layerBounds) {
        fitLayerBounds(map, layerBounds, initialView, "data");
      } else {
        frameMadridCity(map, initialView);
      }
      return;
    }

    if (!hasUbic && !hasSigma) {
      if (lastFitKey.current !== key) {
        frameMadridCity(map, initialView);
        lastFitKey.current = key;
      }
      return;
    }

    if (lastFitKey.current === key) return;
    lastFitKey.current = key;

    const layerBounds = boundsFromLayers();
    if (layerBounds) {
      fitLayerBounds(map, layerBounds, initialView, "data");
      return;
    }
    frameMadridCity(map, initialView);
  }, [map, ubicaciones, sigma, fitToData, initialView]);

  return null;
}

function FlyToNdp({
  geojson,
  ndp,
}: {
  geojson: UbicacionesMapGeoJson | null;
  ndp: string | null;
}) {
  const map = useMap();
  useEffect(() => {
    if (!ndp || !geojson) return;
    const f = geojson.features.find((x) => x.properties.ndp === ndp);
    if (!f) return;
    const [lng, lat] = f.geometry.coordinates;
    map.flyTo([lat, lng], 17, { duration: 0.55 });
  }, [map, geojson, ndp]);
  return null;
}

export function MadridUnifiedMap({
  ubicacionesGeojson,
  sigmaGeojson,
  highlightNdp,
  onSelectNdp,
  sigmaPopupOptions,
  showUbicaciones = true,
  showSigma = true,
  onBoundsChange,
  statsHint,
  className = "",
  interactive = true,
  fitToData = true,
  initialView = "city",
  preferCanvas = false,
}: {
  ubicacionesGeojson: UbicacionesMapGeoJson | null;
  sigmaGeojson: SectorFeatureCollection | null;
  highlightNdp: string | null;
  onSelectNdp: (ndp: string) => void;
  sigmaPopupOptions?: FeaturePopupOptions | null;
  showUbicaciones?: boolean;
  showSigma?: boolean;
  onBoundsChange?: (bounds: MapBounds) => void;
  statsHint?: string | null;
  className?: string;
  /** Vista previa (inicio): sin pan/zoom; el contenedor padre enlaza a /explore. */
  interactive?: boolean;
  /**
   * Si false, encuadre fijo (p. ej. portada con `initialView="preview"` y sigma cargado).
   * `city` = Madrid capital; `preview` = más zoom para la miniatura de inicio.
   */
  fitToData?: boolean;
  /** Zoom inicial: `preview` portada, `explore` mapa explorar, `city` encaje por datos. */
  initialView?: MapInitialView;
  /** Mejor rendimiento con muchos polígonos en móvil. */
  preferCanvas?: boolean;
}) {
  const fitPreset = FIT_PRESETS[initialView] ?? FIT_PRESETS.city;
  const { ready: mapReady, mapKey } = useLeafletMount();
  const nSigma = sigmaGeojson?.features?.length ?? 0;
  const nUbic = ubicacionesGeojson?.features?.length ?? 0;

  const statsLabel = useMemo((): ReactNode | null => {
    if (statsHint) return statsHint;
    const parts: ReactNode[] = [];
    if (showSigma && nSigma > 0) {
      parts.push(
        <span key="sigma">
          <span className="font-semibold text-slate-800">{nSigma.toLocaleString("es-ES")}</span> en vista
        </span>,
      );
    }
    if (showSigma && showUbicaciones && nSigma > 0 && nUbic > 0) {
      parts.push(<span key="sep"> · </span>);
    }
    if (showUbicaciones && nUbic > 0) {
      parts.push(
        <span key="ubic">
          <span className="font-semibold text-slate-800">{nUbic.toLocaleString("es-ES")}</span> edificios
        </span>,
      );
    }
    return parts.length > 0 ? parts : null;
  }, [statsHint, showSigma, showUbicaciones, nSigma, nUbic]);

  const legend = useMemo(
    () => (
      <div className="pointer-events-none absolute bottom-12 left-3 z-[1000] hidden max-h-[min(40vh,280px)] max-w-[calc(100%-5rem)] flex-col gap-1.5 overflow-y-auto rounded-xl border border-white/90 bg-white/92 px-3 py-2.5 text-[11px] text-slate-600 shadow-md backdrop-blur-sm sm:bottom-14 sm:flex">
        {showSigma ? (
          <>
            <span className="flex items-center gap-2">
              <span className={SIGMA_MAP_LEGEND.planeamiento} />
              {PROYECTOS} · planeamiento
            </span>
            <span className="flex items-center gap-2">
              <span className={SIGMA_MAP_LEGEND.tramitacion} />
              {PROYECTOS} · en tramitación
            </span>
          </>
        ) : null}
        {showUbicaciones ? <LicenciaMapLegend /> : null}
      </div>
    ),
    [showSigma, showUbicaciones],
  );

  return (
    <div className={`homes-map-shell group relative w-full ${className}`}>
      <div
        className="pointer-events-none absolute inset-0 z-[500] rounded-none ring-1 ring-black/[0.05] ring-inset"
        aria-hidden
      />
      <div className="absolute inset-0 overflow-hidden bg-teal-50/40">
        {statsLabel ? (
          <div className="pointer-events-none absolute bottom-3 left-1/2 z-[1000] flex w-[min(calc(100%-1.5rem),28rem)] -translate-x-1/2 justify-center px-3 sm:bottom-4">
            <p className="rounded-xl border border-white/90 bg-white/92 px-3 py-1.5 text-center text-xs leading-snug text-slate-600 shadow-md backdrop-blur-sm">
              {statsLabel}
            </p>
          </div>
        ) : null}

        {legend}

        {mapReady ? (
          <MapContainer
            key={mapKey}
            center={MADRID_CENTER}
            zoom={fitPreset.defaultZoom}
            className="z-0 h-full w-full"
            style={{ height: "100%", width: "100%" }}
            zoomControl={false}
            scrollWheelZoom={interactive}
            dragging={interactive}
            doubleClickZoom={interactive}
            touchZoom={interactive}
            boxZoom={interactive}
            keyboard={interactive}
            attributionControl={false}
            preferCanvas={preferCanvas}
          >
            <TileLayer url={HOMES_MAP_TILE_URL} />
            <MapSizeFix />
            {interactive && onBoundsChange ? (
              <MapBoundsReporter onBoundsChange={onBoundsChange} />
            ) : null}
            <LicenciasClusterLayer
              geojson={ubicacionesGeojson}
              highlightNdp={highlightNdp}
              onSelectNdp={onSelectNdp}
              visible={showUbicaciones}
            />
            <SigmaPolygonsLayer
              geojson={sigmaGeojson}
              popupOptions={sigmaPopupOptions ?? null}
              visible={showSigma}
              preview={!interactive}
            />
            <UnifiedFitBounds
              ubicaciones={ubicacionesGeojson}
              sigma={sigmaGeojson}
              fitToData={fitToData}
              initialView={initialView}
            />
            <FlyToNdp geojson={ubicacionesGeojson} ndp={highlightNdp} />
            {interactive ? <ZoomControl position="topright" /> : null}
            {interactive ? <ScaleControl position="bottomleft" imperial={false} /> : null}
          </MapContainer>
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
            Iniciando mapa…
          </div>
        )}

        <div className="pointer-events-none absolute bottom-2 right-2 z-[1000] text-right text-[9px] text-slate-400/90">
          <span className="pointer-events-auto">
            <a
              href="https://www.openstreetmap.org/copyright"
              className="underline decoration-slate-300/80"
              target="_blank"
              rel="noopener noreferrer"
            >
              © OSM
            </a>
            {" · CARTO"}
          </span>
        </div>
      </div>
    </div>
  );
}
