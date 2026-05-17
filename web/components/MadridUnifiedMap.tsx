"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  GeoJSON,
  MapContainer,
  ScaleControl,
  TileLayer,
  ZoomControl,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import type { CircleMarkerOptions, LatLngExpression, PathOptions } from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.markercluster";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { collectMapBounds } from "@/lib/map-bounds";
import {
  featureLayerStyle,
  featurePointStyle,
  featurePopupHtml,
  type FeaturePopupOptions,
  type SectorFeatureCollection,
} from "@/lib/sector-geo";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import {
  createLicenciaDivIcon,
  clasificarLicenciaMapa,
  licenciaMapTooltipLabel,
} from "@/lib/licencia-mapa";
import { LicenciaMapLegend } from "@/components/map/LicenciaMapLegend";
import { MapBoundsReporter } from "@/components/map/MapBoundsReporter";
import { MapSizeFix } from "@/components/map/MapSizeFix";
import type { MapBounds } from "@/lib/map-viewport";
import type { UbicacionMapProperties } from "@/lib/ubicacion";
import { LICENCIA_MAPA_CONFIG, type LicenciaMapaCategoria } from "@/lib/licencia-mapa";
import { PROYECTOS } from "@/lib/ui-labels";
import { useLeafletMount } from "@/lib/use-leaflet-mount";

type LeafletWithCluster = typeof L & {
  markerClusterGroup: (options?: object) => L.LayerGroup;
};
const Lc = L as LeafletWithCluster;

const MADRID_CENTER: LatLngExpression = [40.42, -3.703];
const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

type UbicacionGeo = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: UbicacionMapProperties;
  }>;
};

function UnifiedFitBounds({
  ubicaciones,
  sigma,
}: {
  ubicaciones: UbicacionGeo | null;
  sigma: SectorFeatureCollection | null;
}) {
  const map = useMap();
  const didFit = useRef(false);
  useEffect(() => {
    if (didFit.current) return;
    const hasUbic = Boolean(ubicaciones?.features?.length);
    const hasSigma = Boolean(sigma?.features?.length);
    if (!hasUbic && !hasSigma) {
      map.setView(MADRID_CENTER, 11, { animate: false });
      return;
    }
    didFit.current = true;
    if (hasUbic) {
      const ub = L.geoJSON(ubicaciones as GeoJSON.FeatureCollection).getBounds();
      if (ub.isValid()) {
        map.fitBounds(ub, { padding: [48, 48], maxZoom: 12, animate: false });
        return;
      }
    }
    const bounds = collectMapBounds([], sigma);
    if (bounds) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 11, animate: false });
    else map.setView(MADRID_CENTER, 11, { animate: false });
  }, [map, ubicaciones, sigma]);
  return null;
}

function FlyToNdp({
  geojson,
  ndp,
}: {
  geojson: UbicacionGeo | null;
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

function circleStyleFor(cat: LicenciaMapaCategoria, hi: boolean): CircleMarkerOptions {
  const bg = LICENCIA_MAPA_CONFIG[cat]?.bg ?? "#64748b";
  return {
    radius: hi ? 8 : 5,
    fillColor: bg,
    color: "#fff",
    weight: hi ? 2 : 1,
    fillOpacity: hi ? 1 : 0.85,
  };
}

function UbicacionesCluster({
  geojson,
  highlightNdp,
  onSelectNdp,
  visible,
}: {
  geojson: UbicacionGeo | null;
  highlightNdp: string | null;
  onSelectNdp: (ndp: string) => void;
  visible: boolean;
}) {
  const map = useMap();
  const clusterRef = useRef<L.LayerGroup | null>(null);
  const zoomRef = useRef(map.getZoom());

  useEffect(() => {
    const onZoom = () => {
      zoomRef.current = map.getZoom();
    };
    map.on("zoomend", onZoom);
    return () => {
      map.off("zoomend", onZoom);
    };
  }, [map]);

  useEffect(() => {
    if (!visible || !geojson?.features?.length) {
      if (clusterRef.current) {
        map.removeLayer(clusterRef.current);
        clusterRef.current = null;
      }
      return;
    }

    const cluster = Lc.markerClusterGroup({
      chunkedLoading: true,
      chunkInterval: 200,
      chunkDelay: 30,
      maxClusterRadius: 52,
      spiderfyOnMaxZoom: false,
      showCoverageOnHover: false,
      disableClusteringAtZoom: 16,
    });

    const useSimple = map.getZoom() < 14;

    const layer = L.geoJSON(geojson as GeoJSON.FeatureCollection, {
      pointToLayer(feature, latlng) {
        const p = feature.properties as UbicacionMapProperties;
        const isHi = Boolean(highlightNdp && p.ndp === highlightNdp);
        const cat = clasificarLicenciaMapa(p.ultimaLicenciaTipo);
        if (useSimple && !isHi) {
          return L.circleMarker(latlng, circleStyleFor(cat, isHi));
        }
        return L.marker(latlng, {
          icon: createLicenciaDivIcon(cat, isHi),
        });
      },
      onEachFeature(feature, lyr) {
        const p = feature.properties as UbicacionMapProperties;
        lyr.on("click", () => onSelectNdp(p.ndp));
        if (map.getZoom() >= 14) {
          const label = licenciaMapTooltipLabel(p.ultimaLicenciaTipo, p.direccion);
          lyr.bindTooltip(label, { direction: "top", opacity: 0.95, sticky: true });
        }
      },
    });

    cluster.addLayer(layer);
    map.addLayer(cluster);
    clusterRef.current = cluster;

    return () => {
      map.removeLayer(cluster);
      clusterRef.current = null;
    };
  }, [map, geojson, highlightNdp, onSelectNdp, visible]);

  return null;
}

function SigmaPolygons({
  geojson,
  popupOptions,
  visible,
}: {
  geojson: SectorFeatureCollection | null;
  popupOptions: FeaturePopupOptions | null;
  visible: boolean;
}) {
  const router = useRouter();

  const onEach = useCallback(
    (feature: GeoJSON.Feature, layer: L.Layer) => {
      const props = feature.properties as Record<string, unknown> | undefined;
      const pop = featurePopupHtml(props, popupOptions ?? undefined);
      layer.bindPopup(pop, {
        className: "homes-map-popup homes-map-popup-sigma",
        maxWidth: 380,
      });
      layer.on("click", () => {
        const expKey = expedienteGrupoKeyFromVariant(String(props?.EXP_TX_NUMERO || ""));
        if (expKey) router.push(sigmaFichaPath(expKey));
      });
    },
    [router, popupOptions],
  );

  if (!visible || !geojson?.features?.length) return null;

  return (
    <GeoJSON
      key={`sigma-${geojson.features.length}`}
      data={geojson as never}
      style={(feature) => {
        const geomType = feature?.geometry?.type;
        const props = feature?.properties;
        return featureLayerStyle(props, geomType) as PathOptions;
      }}
      pointToLayer={(feature, latlng) =>
        L.circleMarker(
          latlng,
          featurePointStyle(feature?.properties) as PathOptions,
        )
      }
      onEachFeature={onEach}
    />
  );
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
}: {
  ubicacionesGeojson: UbicacionGeo | null;
  sigmaGeojson: SectorFeatureCollection | null;
  highlightNdp: string | null;
  onSelectNdp: (ndp: string) => void;
  sigmaPopupOptions?: FeaturePopupOptions | null;
  showUbicaciones?: boolean;
  showSigma?: boolean;
  onBoundsChange?: (bounds: MapBounds) => void;
  statsHint?: string | null;
  className?: string;
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
              <span className="h-2.5 w-4 rounded-sm bg-sky-400/90 ring-1 ring-sky-700" />
              {PROYECTOS} · planeamiento
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-4 rounded-sm bg-amber-400/90 ring-1 ring-amber-700" />
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
      <div className="relative h-full w-full overflow-hidden bg-slate-100">
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
            scrollWheelZoom
            attributionControl={false}
          >
            <TileLayer url={TILE_URL} />
            <MapSizeFix />
            {onBoundsChange ? <MapBoundsReporter onBoundsChange={onBoundsChange} /> : null}
            <SigmaPolygons
              geojson={sigmaGeojson}
              popupOptions={sigmaPopupOptions ?? null}
              visible={showSigma}
            />
            <UbicacionesCluster
              geojson={ubicacionesGeojson}
              highlightNdp={highlightNdp}
              onSelectNdp={onSelectNdp}
              visible={showUbicaciones}
            />
            <UnifiedFitBounds ubicaciones={ubicacionesGeojson} sigma={sigmaGeojson} />
            <FlyToNdp geojson={ubicacionesGeojson} ndp={highlightNdp} />
            <ZoomControl position="topright" />
            <ScaleControl position="bottomleft" imperial={false} />
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
