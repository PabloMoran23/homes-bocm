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
      chunkInterval: 120,
      maxClusterRadius: 52,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    });

    const layer = L.geoJSON(geojson as unknown as GeoJSON.FeatureCollection, {
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
        lyr.bindTooltip(label, { direction: "top", opacity: 0.95, sticky: true });
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

    cluster.addLayer(layer);
    map.addLayer(cluster);
    clusterRef.current = cluster;

    return () => {
      map.removeLayer(cluster);
      clusterRef.current = null;
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
