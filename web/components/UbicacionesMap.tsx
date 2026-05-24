"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
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
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.markercluster";
import {
  clasificarLicenciaMapaDesdeActuacion,
  createLicenciaDivIcon,
  licenciaMapTooltipLabel,
} from "@/lib/licencia-mapa";
import { HOMES_MAP_ATTRIBUTION, HOMES_MAP_TILE_URL } from "@/lib/map-tiles";
import { actuacionDesdeMapProps, type UbicacionMapProperties } from "@/lib/ubicacion";

type LeafletWithCluster = typeof L & {
  markerClusterGroup: (options?: object) => L.LayerGroup;
};
const Lc = L as LeafletWithCluster;

const MADRID_CENTER: LatLngExpression = [40.42, -3.703];

type GeoFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: UbicacionMapProperties;
};

type GeoCollection = {
  type: "FeatureCollection";
  features: GeoFeature[];
};

function MarkerClusterLayer({
  geojson,
  highlightNdp,
  onSelect,
}: {
  geojson: GeoCollection;
  highlightNdp: string | null;
  onSelect: (ndp: string) => void;
}) {
  const map = useMap();
  const clusterRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!map) return;

    const cluster = Lc.markerClusterGroup({
      chunkedLoading: true,
      chunkInterval: 120,
      maxClusterRadius: 52,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });

    const layer = L.geoJSON(geojson as GeoJSON.FeatureCollection, {
      pointToLayer(feature, latlng) {
        const p = feature.properties as UbicacionMapProperties;
        const isHi = Boolean(highlightNdp && p.ndp === highlightNdp);
        const cat = clasificarLicenciaMapaDesdeActuacion(actuacionDesdeMapProps(p));
        return L.marker(latlng, {
          icon: createLicenciaDivIcon(cat, isHi),
        });
      },
      onEachFeature(feature, layer) {
        const p = feature.properties as UbicacionMapProperties;
        const label = licenciaMapTooltipLabel(actuacionDesdeMapProps(p), p.direccion);
        const extra = [p.distrito, p.licencias ? `${p.licencias} lic.` : null]
          .filter(Boolean)
          .join(" · ");
        layer.bindTooltip(extra ? `${label} (${extra})` : label, { direction: "top", opacity: 0.95 });
        layer.on("click", () => onSelect(p.ndp));
      },
    });

    cluster.addLayer(layer);
    map.addLayer(cluster);
    clusterRef.current = cluster;

    return () => {
      map.removeLayer(cluster);
      clusterRef.current = null;
    };
  }, [map, geojson, highlightNdp, onSelect]);

  useEffect(() => {
    if (!highlightNdp || !clusterRef.current) return;
    const walk = (layer: L.Layer) => {
      if (layer instanceof L.Marker) {
        const feat = (layer as L.Marker & { feature?: GeoFeature }).feature;
        const p = feat?.properties;
        if (!p) return;
        const isHi = p.ndp === highlightNdp;
        const cat = clasificarLicenciaMapaDesdeActuacion(actuacionDesdeMapProps(p));
        layer.setIcon(createLicenciaDivIcon(cat, isHi));
        return;
      }
      if (layer instanceof L.LayerGroup) {
        layer.eachLayer(walk);
      }
    };
    clusterRef.current.eachLayer(walk);
  }, [highlightNdp]);

  return null;
}

function FlyToHighlight({
  geojson,
  highlightNdp,
}: {
  geojson: GeoCollection;
  highlightNdp: string | null;
}) {
  const map = useMap();
  useEffect(() => {
    if (!highlightNdp) return;
    const f = geojson.features.find((x) => x.properties.ndp === highlightNdp);
    if (!f) return;
    const [lng, lat] = f.geometry.coordinates;
    map.flyTo([lat, lng], 17, { duration: 0.6 });
  }, [map, geojson, highlightNdp]);
  return null;
}

export function UbicacionesMap({
  geojson,
  highlightNdp,
  onSelectNdp,
  className = "",
}: {
  geojson: GeoCollection;
  highlightNdp: string | null;
  onSelectNdp: (ndp: string) => void;
  className?: string;
}) {
  const onSelect = useCallback(
    (ndp: string) => {
      onSelectNdp(ndp);
    },
    [onSelectNdp],
  );

  const bounds = useMemo(() => {
    if (!geojson.features.length) return null;
    return L.geoJSON(geojson as GeoJSON.FeatureCollection).getBounds();
  }, [geojson]);

  return (
    <div
      className={`homes-map-shell overflow-hidden rounded-xl border border-teal-100/80 bg-teal-50/40 shadow-sm ${className}`}
    >
      <MapContainer
        center={MADRID_CENTER}
        zoom={11}
        className="h-full w-full min-h-[min(70vh,640px)]"
        zoomControl={false}
        scrollWheelZoom
      >
        <TileLayer attribution={HOMES_MAP_ATTRIBUTION} url={HOMES_MAP_TILE_URL} />
        <ZoomControl position="topright" />
        <ScaleControl position="bottomleft" imperial={false} />
        {bounds ? (
          <FlyToHighlight geojson={geojson} highlightNdp={highlightNdp} />
        ) : null}
        <MarkerClusterLayer
          geojson={geojson}
          highlightNdp={highlightNdp}
          onSelect={onSelect}
        />
      </MapContainer>
    </div>
  );
}
