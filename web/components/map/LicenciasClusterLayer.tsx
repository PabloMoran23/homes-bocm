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
  licenciaMapTooltipLabel,
} from "@/lib/licencia-mapa";
import { actuacionDesdeMapProps, type UbicacionMapProperties } from "@/lib/ubicacion";
import { boundsFromLeaflet, filterPointFeaturesInView } from "@/lib/map-viewport";

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

function buildMarkersLayer(
  geojson: UbicacionGeo,
  highlightNdp: string | null,
  onSelectNdp: (ndp: string) => void,
  stickyTooltips: boolean,
) {
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
      lyr.on("click", () => onSelectNdp(p.ndp));
      const label = licenciaMapTooltipLabel(actuacionDesdeMapProps(p), p.direccion);
      lyr.bindTooltip(label, { direction: "top", opacity: 0.95, sticky: stickyTooltips });
      const lic = p.licencias;
      if (lic > 1) {
        lyr.bindPopup(
          `<div class="text-sm"><strong>${p.direccion ?? "Edificio"}</strong><br/>` +
            `<span class="text-slate-600">${lic.toLocaleString("es-ES")} licencias registradas</span></div>`,
          { className: "homes-map-popup", maxWidth: 280 },
        );
      }
    },
  });
}

export function LicenciasClusterLayer({
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
  const geojsonRef = useRef(geojson);
  const highlightRef = useRef(highlightNdp);
  const onSelectRef = useRef(onSelectNdp);
  const stickyTooltipsRef = useRef(false);
  geojsonRef.current = geojson;
  highlightRef.current = highlightNdp;
  onSelectRef.current = onSelectNdp;

  useEffect(() => {
    stickyTooltipsRef.current = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  }, []);

  /** Monta el grupo de clusters una sola vez. */
  useEffect(() => {
    if (!visible) {
      if (clusterRef.current) {
        map.removeLayer(clusterRef.current);
        clusterRef.current = null;
      }
      return;
    }

    const cluster = Lc.markerClusterGroup({
      chunkedLoading: true,
      chunkInterval: 120,
      maxClusterRadius: 52,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });
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

      const layer = buildMarkersLayer(
        { features: feats },
        highlightRef.current,
        onSelectRef.current,
        stickyTooltipsRef.current,
      );
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
  }, [map, geojson, highlightNdp, onSelectNdp, visible]);

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
