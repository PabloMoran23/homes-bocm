"use client";

import { useEffect, useMemo, useRef } from "react";
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

function UnifiedFitBounds({
  ubicaciones,
  sigma,
  fitToData = true,
}: {
  ubicaciones: UbicacionesMapGeoJson | null;
  sigma: SectorFeatureCollection | null;
  fitToData?: boolean;
}) {
  const map = useMap();
  const lastFitKey = useRef("");

  useEffect(() => {
    if (!fitToData) {
      map.setView(MADRID_CENTER, 11, { animate: false });
      return;
    }

    const hasUbic = Boolean(ubicaciones?.features?.length);
    const hasSigma = Boolean(sigma?.features?.length);
    const key = `${hasUbic ? ubicaciones!.features.length : 0}:${hasSigma ? sigma!.features.length : 0}`;

    if (!hasUbic && !hasSigma) {
      if (lastFitKey.current !== key) {
        map.setView(MADRID_CENTER, 11, { animate: false });
        lastFitKey.current = key;
      }
      return;
    }

    if (lastFitKey.current === key) return;
    lastFitKey.current = key;

    let bounds: L.LatLngBounds | null = null;
    if (hasSigma) {
      const sb = L.geoJSON(sigma as GeoJSON.FeatureCollection).getBounds();
      if (sb.isValid()) bounds = sb;
    }
    if (hasUbic) {
      const ub = L.geoJSON(ubicaciones as GeoJSON.FeatureCollection).getBounds();
      if (ub.isValid()) bounds = bounds ? bounds.extend(ub) : ub;
    }
    if (bounds?.isValid()) {
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: 12, animate: false });
      return;
    }
    map.setView(MADRID_CENTER, 11, { animate: false });
  }, [map, ubicaciones, sigma, fitToData]);

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
  /** Si false, vista fija sobre Madrid (evita getBounds sobre miles de polígonos). */
  fitToData?: boolean;
  /** Mejor rendimiento con muchos polígonos en móvil. */
  preferCanvas?: boolean;
}) {
  const { ready: mapReady, mapKey } = useLeafletMount();
  const nSigma = sigmaGeojson?.features?.length ?? 0;
  const nUbic = ubicacionesGeojson?.features?.length ?? 0;

  const legend = useMemo(
    () => (
      <div className="pointer-events-none absolute bottom-3 left-3 z-[1000] hidden max-h-[min(40vh,280px)] max-w-[calc(100%-5rem)] flex-col gap-1.5 overflow-y-auto rounded-xl border border-white/90 bg-white/92 px-3 py-2.5 text-[11px] text-slate-600 shadow-md backdrop-blur-sm sm:flex">
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
    <div className={`homes-map-shell group relative h-full min-h-0 w-full ${className}`}>
      <div
        className="pointer-events-none absolute inset-0 z-[500] rounded-none ring-1 ring-black/[0.05] ring-inset"
        aria-hidden
      />
      <div className="relative h-full w-full overflow-hidden bg-teal-50/40">
        <div className="pointer-events-none absolute left-0 right-0 top-0 z-[1000] flex items-start justify-between gap-2 p-2 sm:gap-3 sm:p-4">
          <div className="pointer-events-auto max-w-[min(100%,14rem)] rounded-xl border border-white/80 bg-white/90 px-2.5 py-1.5 shadow-md backdrop-blur-md sm:max-w-none sm:px-3 sm:py-2">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--portal-accent)]">
              Madrid
            </p>
            <p className="text-xs text-slate-600">
              {statsHint ?? (
                <>
                  {showSigma && nSigma > 0 ? (
                    <span>
                      <span className="font-semibold text-slate-800">{nSigma.toLocaleString("es-ES")}</span>{" "}
                      en vista
                    </span>
                  ) : null}
                  {showSigma && showUbicaciones && nSigma > 0 && nUbic > 0 ? " · " : null}
                  {showUbicaciones && nUbic > 0 ? (
                    <span>
                      <span className="font-semibold text-slate-800">{nUbic.toLocaleString("es-ES")}</span>{" "}
                      edificios
                    </span>
                  ) : null}
                </>
              )}
            </p>
          </div>
        </div>

        {legend}

        {mapReady ? (
          <MapContainer
            key={mapKey}
            center={MADRID_CENTER}
            zoom={11}
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
