"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  MapContainer,
  ScaleControl,
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
} from "@/lib/licencia-mapa";
import { HomesBasemapLayer } from "@/components/map/HomesBasemapLayer";
import { HOMES_MAP_MAX_ZOOM, HOMES_MAP_MIN_ZOOM } from "@/lib/map-tiles";
import { bindMapHoverPopup } from "@/lib/map-hover-popup";
import { actuacionDesdeMapProps, type UbicacionMapProperties } from "@/lib/ubicacion";
import { ubicacionMapPopupHtml } from "@/lib/ubicacion-map-popup";

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
  onSelect: _onSelect,
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
        bindMapHoverPopup(layer, ubicacionMapPopupHtml(p), { maxWidth: 300 });
      },
    });

    cluster.addLayer(layer);
    map.addLayer(cluster);
    clusterRef.current = cluster;

    return () => {
      map.removeLayer(cluster);
      clusterRef.current = null;
    };
  }, [map, geojson, highlightNdp]);

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
      className={`homes-map-shell overflow-hidden rounded-xl border border-[var(--portal-paper-deep)] bg-[var(--portal-paper)] shadow-sm ${className}`}
    >
      <MapContainer
        center={MADRID_CENTER}
        zoom={11}
        minZoom={HOMES_MAP_MIN_ZOOM}
        maxZoom={HOMES_MAP_MAX_ZOOM}
        className="h-full w-full min-h-[min(70vh,640px)]"
        zoomControl={false}
        scrollWheelZoom
      >
        <HomesBasemapLayer />
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
