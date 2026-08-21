"use client";

import { useEffect, useMemo, useRef, type ReactNode } from "react";
import {
  MapContainer,
  ScaleControl,
  ZoomControl,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { LicenciasClusterLayer } from "@/components/map/LicenciasClusterLayer";
import { PortalProyectosClusterLayer } from "@/components/map/PortalProyectosClusterLayer";
import { PortalProyectosPolygonLayer } from "@/components/map/PortalProyectosPolygonLayer";
import { SigmaPolygonsLayer } from "@/components/map/SigmaPolygonsLayer";
import { LandingMapPulseLayer } from "@/components/map/LandingMapPulseLayer";
import { LandingMapTourLayer } from "@/components/map/LandingMapTourLayer";
import { MapSelectionClearLayer } from "@/components/map/MapSelectionClearLayer";
import type { LandingMapSpotlightItem } from "@/lib/landing-map-spotlight";
import type { LandingTourActiveChange } from "@/lib/landing-map-tour";
import type { FeaturePopupOptions, SectorFeatureCollection } from "@/lib/sector-geo";
import { LicenciaMapLegend } from "@/components/map/LicenciaMapLegend";
import { MapBoundsReporter } from "@/components/map/MapBoundsReporter";
import { MapSizeFix } from "@/components/map/MapSizeFix";
import type { MapBounds } from "@/lib/map-viewport";
import type { UbicacionesMapGeoJson } from "@/lib/madrid-ubicaciones-map";
import type { CmPortalGeoJson, CmPortalProyectoProps } from "@/lib/cm-portal-geo";
import type { MapScope } from "@/lib/map-scope";
import { SIGMA_MAP_LEGEND } from "@/lib/map-sigma-colors";
import { PROYECTOS } from "@/lib/ui-labels";
import { useLeafletMount } from "@/lib/use-leaflet-mount";
import { usePreferCanvas } from "@/lib/use-prefer-canvas";
import { capZoomForContainer, fixedZoomForContainer } from "@/lib/map-visual-scale";
import { HomesBasemapLayer } from "@/components/map/HomesBasemapLayer";
import { HOMES_MAP_MAX_ZOOM, HOMES_MAP_MIN_ZOOM } from "@/lib/map-tiles";

const MADRID_CENTER: LatLngExpression = [40.42, -3.703];

/** Vista por defecto al abrir /explore (ciudad entera). */
const MADRID_CITY_ZOOM = 11;
const MADRID_FIT_MAX_ZOOM = 14;
const MADRID_CITY_BOUNDS = L.latLngBounds(
  [40.348, -3.888],
  [40.502, -3.518],
);

/** Vista Comunidad de Madrid (modo local `NEXT_PUBLIC_MAP_SCOPE=cm`). */
const CM_BOUNDS = L.latLngBounds(
  [39.85, -4.85],
  [41.15, -3.15],
);
const CM_CENTER: LatLngExpression = [40.45, -3.65];
const CM_EXPLORE_ZOOM = 9;

/** Portada: zoom fijo (un poco más alejado que explorar para la miniatura). */
const MADRID_PREVIEW_ZOOM = 10;

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

function fitBoundsForContainer(
  map: L.Map,
  bounds: L.LatLngBounds,
  opts: L.FitBoundsOptions,
  view?: MapInitialView,
) {
  const el = map.getContainer();
  const w = el?.clientWidth ?? 800;
  const h = el?.clientHeight ?? 400;
  const maxZoom =
    opts.maxZoom != null && view !== "preview"
      ? capZoomForContainer(opts.maxZoom, w, h, 9)
      : opts.maxZoom;
  map.fitBounds(bounds, { ...opts, maxZoom });
}

function frameMadridCity(map: L.Map, view: MapInitialView) {
  const bounds = view === "preview" ? MADRID_PREVIEW_BOUNDS : MADRID_CITY_BOUNDS;
  fitBoundsForContainer(map, bounds, FIT_PRESETS[view].city, view);
}

function frameCmRegion(map: L.Map) {
  fitBoundsForContainer(
    map,
    CM_BOUNDS,
    { padding: [24, 24], maxZoom: CM_EXPLORE_ZOOM, animate: false },
    "explore",
  );
}

/** Zoom fijo; no usar getBounds() del GeoJSON (cubre todo Madrid y aleja el mapa). */
function frameFixedZoom(map: L.Map, view: MapInitialView) {
  const zoom = FIXED_VIEW_ZOOM[view];
  if (zoom == null) return;
  const el = map.getContainer();
  const w = el?.clientWidth ?? 800;
  const h = el?.clientHeight ?? 400;
  // Portada: zoom fijo sin boost en móvil (evita polígonos “gordos” en miniatura).
  const effective =
    view === "preview" ? zoom : fixedZoomForContainer(zoom, w, h);
  map.setView(MADRID_CENTER, effective, { animate: false });
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
  fitBoundsForContainer(map, bounds, FIT_PRESETS[view][mode], view);
}

function UnifiedFitBounds({
  ubicaciones,
  sigma,
  portal,
  portalPolygons,
  fitToData = true,
  initialView = "city",
  mapScope = "madrid",
}: {
  ubicaciones: UbicacionesMapGeoJson | null;
  sigma: SectorFeatureCollection | null;
  portal?: CmPortalGeoJson<CmPortalProyectoProps> | null;
  portalPolygons?: CmPortalGeoJson<CmPortalProyectoProps> | null;
  fitToData?: boolean;
  initialView?: MapInitialView;
  mapScope?: MapScope;
}) {
  const map = useMap();
  const lastFitKey = useRef("");
  /** Zoom fijo de portada/explorar: solo al montar (no al cambiar features en vista). */
  const fixedExploreZoomDone = useRef(false);

  useEffect(() => {
    const hasUbic = Boolean(ubicaciones?.features?.length);
    const hasSigma = Boolean(sigma?.features?.length);
    const hasPortal = Boolean(portal?.features?.length);
    const hasPortalPolys = Boolean(portalPolygons?.features?.length);
    const key = `${mapScope}:${initialView}:${fitToData}:${hasUbic ? ubicaciones!.features.length : 0}:${hasSigma ? sigma!.features.length : 0}:${hasPortal ? portal!.features.length : 0}:${hasPortalPolys ? portalPolygons!.features.length : 0}`;

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
      if (hasPortal) {
        const pb = L.geoJSON(portal as GeoJSON.FeatureCollection).getBounds();
        if (pb.isValid()) bounds = bounds ? bounds.extend(pb) : pb;
      }
      if (hasPortalPolys) {
        const pp = L.geoJSON(portalPolygons as GeoJSON.FeatureCollection).getBounds();
        if (pp.isValid()) bounds = bounds ? bounds.extend(pp) : pp;
      }
      return bounds?.isValid() ? bounds : null;
    };

    if (!fitToData) {
      if (mapScope === "cm" && initialView === "explore") {
        if (fixedExploreZoomDone.current) return;
        fixedExploreZoomDone.current = true;
        frameCmRegion(map);
        return;
      }
      if (initialView === "preview" || initialView === "explore") {
        if (fixedExploreZoomDone.current) return;
        fixedExploreZoomDone.current = true;
        return scheduleFixedZoom(map, initialView);
      }

      if (lastFitKey.current === key) return;
      lastFitKey.current = key;

      const layerBounds = boundsFromLayers();
      if (layerBounds) {
        fitLayerBounds(map, layerBounds, initialView, "data");
      } else {
        frameMadridCity(map, initialView);
      }
      return;
    }

    if (!hasUbic && !hasSigma && !hasPortal && !hasPortalPolys) {
      if (lastFitKey.current !== key) {
        if (mapScope === "cm") frameCmRegion(map);
        else frameMadridCity(map, initialView);
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
  }, [map, ubicaciones, sigma, portal, portalPolygons, fitToData, initialView, mapScope]);

  useEffect(() => {
    if (!fitToData && (initialView === "preview" || initialView === "explore")) return;

    const el = map.getContainer();
    if (!el || typeof ResizeObserver === "undefined") return;

    const refit = () => {
      if (!fitToData) {
        const hasSigma = Boolean(sigma?.features?.length);
        const hasUbic = Boolean(ubicaciones?.features?.length);
        const hasPortal = Boolean(portal?.features?.length);
        const hasPortalPolys = Boolean(portalPolygons?.features?.length);
        if (hasSigma || hasUbic || hasPortal || hasPortalPolys) {
          let bounds: L.LatLngBounds | null = null;
          if (hasSigma) {
            const sb = L.geoJSON(sigma as GeoJSON.FeatureCollection).getBounds();
            if (sb.isValid()) bounds = sb;
          }
          if (hasUbic) {
            const ub = L.geoJSON(ubicaciones as GeoJSON.FeatureCollection).getBounds();
            if (ub.isValid()) bounds = bounds ? bounds.extend(ub) : ub;
          }
          if (hasPortal) {
            const pb = L.geoJSON(portal as GeoJSON.FeatureCollection).getBounds();
            if (pb.isValid()) bounds = bounds ? bounds.extend(pb) : pb;
          }
          if (hasPortalPolys) {
            const pp = L.geoJSON(portalPolygons as GeoJSON.FeatureCollection).getBounds();
            if (pp.isValid()) bounds = bounds ? bounds.extend(pp) : pp;
          }
          if (bounds?.isValid()) fitLayerBounds(map, bounds, initialView, "data");
        }
      }
    };

    const ro = new ResizeObserver(refit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [map, ubicaciones, sigma, portal, portalPolygons, fitToData, initialView, mapScope]);

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
    const el = map.getContainer();
    const w = el?.clientWidth ?? 800;
    const h = el?.clientHeight ?? 400;
    map.flyTo([lat, lng], capZoomForContainer(17, w, h), { duration: 0.55 });
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
  preferCanvas: preferCanvasProp = false,
  showAttribution = true,
  landingPulse = false,
  landingTour = false,
  landingTourItems = [],
  tourGeojson = null,
  onLandingTourActiveChange,
  sigmaCardSelection = false,
  selectedSigmaExpediente = null,
  onSelectSigmaExpediente,
  portalGeojson = null,
  portalPolygonGeojson = null,
  showPortal = false,
  mapScope = "madrid",
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
  /** Mejor rendimiento con muchos polígonos en móvil. Si no se pasa, se detecta automáticamente. */
  preferCanvas?: boolean;
  /** Atribución OSM/OpenFreeMap (desactivar si el mapa va dentro de un enlace). */
  showAttribution?: boolean;
  /** Portada animada: proyectos que aparecen y desaparecen (solo visual). */
  landingPulse?: boolean;
  /** Portada: tour entre proyectos destacados con zoom y tarjeta. */
  landingTour?: boolean;
  landingTourItems?: LandingMapSpotlightItem[];
  tourGeojson?: SectorFeatureCollection | null;
  onLandingTourActiveChange?: (change: LandingTourActiveChange) => void;
  /** Explorar: tarjeta de proyecto al pulsar un polígono SIGMA. */
  sigmaCardSelection?: boolean;
  selectedSigmaExpediente?: string | null;
  onSelectSigmaExpediente?: (expedienteGrupo: string | null) => void;
  /** Proyectos de portales municipales CM (modo `mapScope=cm`). */
  portalGeojson?: CmPortalGeoJson<CmPortalProyectoProps> | null;
  portalPolygonGeojson?: CmPortalGeoJson<CmPortalProyectoProps> | null;
  showPortal?: boolean;
  mapScope?: MapScope;
}) {
  const fitPreset = FIT_PRESETS[initialView] ?? FIT_PRESETS.city;
  const { ready: mapReady, mapKey } = useLeafletMount();
  const preferCanvasAuto = usePreferCanvas();
  /** Canvas tapa polígonos SVG del pulse/tour en la portada. */
  const preferCanvas =
    (preferCanvasProp || preferCanvasAuto) && !landingPulse && !landingTour;
  const landingAnimated = landingPulse || landingTour;
  const nSigma = sigmaGeojson?.features?.length ?? 0;
  const nUbic = ubicacionesGeojson?.features?.length ?? 0;
  const nPortal =
    (portalGeojson?.features?.filter(
      (f) => f.properties?.coordSource !== "municipio_centroid_jitter",
    ).length ?? 0) + (portalPolygonGeojson?.features?.length ?? 0);
  const mapCenter = mapScope === "cm" ? CM_CENTER : MADRID_CENTER;
  const mapZoom =
    mapScope === "cm" && initialView === "explore"
      ? CM_EXPLORE_ZOOM
      : fitPreset.defaultZoom;

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
    if (showPortal && nPortal > 0) {
      parts.push(
        <span key="portal">
          <span className="font-semibold text-slate-800">{nPortal.toLocaleString("es-ES")}</span> portales CM
        </span>,
      );
    }
    return parts.length > 0 ? parts : null;
  }, [statsHint, showSigma, showUbicaciones, showPortal, nSigma, nUbic, nPortal]);

  const legend = useMemo(
    () => (
      <div className="pointer-events-none absolute bottom-12 left-3 z-[1000] hidden max-h-[min(40vh,280px)] max-w-[calc(100%-5rem)] flex-col gap-1.5 overflow-y-auto rounded-xl border border-[var(--portal-paper)]/90 bg-[var(--portal-paper)] px-3 py-2.5 text-[11px] text-[var(--portal-ink)]/70 shadow-md md:bg-[var(--portal-paper)]/92 md:backdrop-blur-sm sm:bottom-14 sm:flex">
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
        {showPortal ? (
          <span className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#c07f6c] ring-2 ring-[var(--portal-paper)]" />
            Portales municipales CM
          </span>
        ) : null}
      </div>
    ),
    [showSigma, showUbicaciones, showPortal],
  );

  return (
    <div className={`homes-map-shell group relative w-full ${className}`}>
      <div
        className="pointer-events-none absolute inset-0 z-[500] rounded-none ring-1 ring-black/[0.05] ring-inset"
        aria-hidden
      />
      <div className="absolute inset-0 overflow-hidden bg-[#f3eee4]">
        {statsLabel ? (
          <div className="pointer-events-none absolute bottom-3 left-1/2 z-[1000] flex w-[min(calc(100%-1.5rem),28rem)] -translate-x-1/2 justify-center px-3 sm:bottom-4">
            <p className="rounded-xl border border-[var(--portal-paper)]/90 bg-[var(--portal-paper)] px-3 py-1.5 text-center text-xs leading-snug text-[var(--portal-ink)]/70 shadow-md md:bg-[var(--portal-paper)]/92 md:backdrop-blur-sm">
              {statsLabel}
            </p>
          </div>
        ) : null}

        {legend}

        {mapReady ? (
          <MapContainer
            key={mapKey}
            center={mapCenter}
            zoom={mapZoom}
            minZoom={HOMES_MAP_MIN_ZOOM}
            maxZoom={HOMES_MAP_MAX_ZOOM}
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
            <HomesBasemapLayer />
            <MapSizeFix />
            {interactive && onBoundsChange ? (
              <MapBoundsReporter onBoundsChange={onBoundsChange} />
            ) : null}
            {sigmaCardSelection && onSelectSigmaExpediente ? (
              <MapSelectionClearLayer onClear={() => onSelectSigmaExpediente(null)} />
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
              visible={showSigma && !landingAnimated}
              preview={!interactive}
              preferCanvas={preferCanvas}
              cardSelection={sigmaCardSelection && interactive}
              selectedExpediente={selectedSigmaExpediente}
              onSelectExpediente={
                onSelectSigmaExpediente
                  ? (grupo) => onSelectSigmaExpediente(grupo)
                  : undefined
              }
            />
            {landingTour && landingTourItems.length > 0 && tourGeojson ? (
              <LandingMapTourLayer
                geojson={tourGeojson}
                items={landingTourItems}
                visible={showSigma}
                onActiveChange={onLandingTourActiveChange ?? (() => {})}
                preferCanvas={preferCanvas}
              />
            ) : landingPulse ? (
              <LandingMapPulseLayer
                geojson={sigmaGeojson}
                visible={showSigma}
                preferCanvas={preferCanvas}
              />
            ) : null}
            <PortalProyectosClusterLayer
              geojson={portalGeojson}
              visible={showPortal}
            />
            <PortalProyectosPolygonLayer
              geojson={portalPolygonGeojson}
              visible={showPortal}
            />
            {landingTour ? null : (
              <UnifiedFitBounds
                ubicaciones={ubicacionesGeojson}
                sigma={sigmaGeojson}
                portal={portalGeojson}
                portalPolygons={portalPolygonGeojson}
                fitToData={fitToData}
                initialView={initialView}
                mapScope={mapScope}
              />
            )}
            <FlyToNdp geojson={ubicacionesGeojson} ndp={highlightNdp} />
            {interactive ? <ZoomControl position="topright" /> : null}
            {interactive ? <ScaleControl position="bottomleft" imperial={false} /> : null}
          </MapContainer>
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
            Iniciando mapa…
          </div>
        )}

        {showAttribution ? (
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
              {" · OpenFreeMap"}
            </span>
          </div>
        ) : (
          <div className="pointer-events-none absolute bottom-2 right-2 z-[1000] text-right text-[9px] text-slate-400/90">
            © OSM · OpenFreeMap
          </div>
        )}
      </div>
    </div>
  );
}
