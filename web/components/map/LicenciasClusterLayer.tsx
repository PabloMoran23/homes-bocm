"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.markercluster";
import {
  createLicenciaDivIcon,
  clasificarLicenciaMapaDesdeActuacion,
} from "@/lib/licencia-mapa";
import { actuacionDesdeMapProps, type UbicacionMapProperties } from "@/lib/ubicacion";
import { boundsFromLeaflet, filterPointFeaturesInView } from "@/lib/map-viewport";
import { bindMapHoverPopup } from "@/lib/map-hover-popup";
import { ubicacionMapPopupHtml } from "@/lib/ubicacion-map-popup";

type LeafletWithCluster = typeof L & {
  markerClusterGroup: (options?: object) => L.LayerGroup;
};
const Lc = L as LeafletWithCluster;

type UbicacionGeo = {
  features: Array<{
    geometry: { coordinates: [number, number] };
    properties: UbicacionMapProperties;
  }>;
};

function clusterOptionsForViewport(): object {
  const mobile =
    typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches;
  return {
    chunkedLoading: true,
    chunkInterval: 120,
    maxClusterRadius: mobile ? 36 : 52,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    disableClusteringAtZoom: mobile ? 14 : 17,
    zoomToBoundsOnClick: true,
  };
}

function buildMarkersLayer(geojson: UbicacionGeo, highlightNdp: string | null) {
  return L.geoJSON(geojson as unknown as GeoJSON.FeatureCollection, {
    pointToLayer(feature, latlng) {
      const p = feature.properties as UbicacionMapProperties;
      const isHi = Boolean(highlightNdp && p.ndp === highlightNdp);
      const cat = clasificarLicenciaMapaDesdeActuacion(actuacionDesdeMapProps(p));
      return L.marker(latlng, {
        icon: createLicenciaDivIcon(cat, isHi),
        zIndexOffset: isHi ? 1000 : 0,
      });
    },
    onEachFeature(feature, lyr) {
      const p = feature.properties as UbicacionMapProperties;
      bindMapHoverPopup(lyr, ubicacionMapPopupHtml(p), { maxWidth: 300 });
    },
  });
}

export function LicenciasClusterLayer({
  geojson,
  highlightNdp,
  onSelectNdp: _onSelectNdp,
  visible,
}: {
  geojson: UbicacionGeo | null;
  highlightNdp: string | null;
  onSelectNdp: (ndp: string) => void;
  visible: boolean;
}) {
  const map = useMap();
  const clusterRef = useRef<L.LayerGroup | null>(null);
  const geojsonRef = useRef(geojson);
  const highlightRef = useRef(highlightNdp);
  geojsonRef.current = geojson;
  highlightRef.current = highlightNdp;

  /** Monta el grupo de clusters una sola vez. */
  useEffect(() => {
    if (!visible) {
      if (clusterRef.current) {
        map.removeLayer(clusterRef.current);
        clusterRef.current = null;
      }
      return;
    }

    const cluster = Lc.markerClusterGroup(clusterOptionsForViewport());
    map.addLayer(cluster);
    clusterRef.current = cluster;

    return () => {
      map.removeLayer(cluster);
      clusterRef.current = null;
    };
  }, [map, visible]);

  /** Refresca markers in-place al cambiar datos o viewport (sin recrear el cluster group). */
  useEffect(() => {
    const cluster = clusterRef.current;
    if (!visible || !cluster) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const refresh = () => {
      if (cancelled) return;
      const data = geojsonRef.current;
      cluster.clearLayers();
      if (!data?.features?.length) return;

      const bounds = boundsFromLeaflet(map.getBounds());
      const feats = filterPointFeaturesInView(data.features, bounds);
      if (!feats.length) return;

      const layer = buildMarkersLayer({ features: feats }, highlightRef.current);
      cluster.addLayer(layer);
    };

    const scheduleRefresh = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(refresh, 80);
    };

    refresh();
    map.on("moveend", scheduleRefresh);
    map.on("zoomend", scheduleRefresh);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      map.off("moveend", scheduleRefresh);
      map.off("zoomend", scheduleRefresh);
    };
  }, [map, geojson, highlightNdp, visible]);

  useEffect(() => {
    if (!highlightNdp || !clusterRef.current) return;
    const walk = (layer: L.Layer) => {
      if (layer instanceof L.Marker) {
        const props = (
          layer as L.Marker & { feature?: { properties?: UbicacionMapProperties } }
        ).feature?.properties;
        if (!props) return;
        const isHi = props.ndp === highlightNdp;
        const cat = clasificarLicenciaMapaDesdeActuacion(actuacionDesdeMapProps(props));
        layer.setIcon(createLicenciaDivIcon(cat, isHi));
        layer.setZIndexOffset(isHi ? 1000 : 0);
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
