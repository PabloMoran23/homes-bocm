"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.markercluster";
import {
  portalProyectoPopupHtml,
  type CmPortalGeoJson,
  type CmPortalProyectoProps,
} from "@/lib/cm-portal-geo";
import { boundsFromLeaflet, filterPointFeaturesInView } from "@/lib/map-viewport";
import { bindMapHoverPopup } from "@/lib/map-hover-popup";

type LeafletWithCluster = typeof L & {
  markerClusterGroup: (options?: object) => L.LayerGroup;
};
const Lc = L as LeafletWithCluster;

function portalDivIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<span style="display:block;width:10px;height:10px;border-radius:50%;background:#7c3aed;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35)"></span>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });
}

function clusterOptionsForViewport(): object {
  const mobile =
    typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches;
  return {
    chunkedLoading: true,
    chunkInterval: 120,
    maxClusterRadius: mobile ? 40 : 56,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    disableClusteringAtZoom: mobile ? 13 : 16,
    zoomToBoundsOnClick: true,
  };
}

function buildMarkersLayer(geojson: CmPortalGeoJson<CmPortalProyectoProps>) {
  return L.geoJSON(geojson as unknown as GeoJSON.FeatureCollection, {
    pointToLayer(_feature, latlng) {
      return L.marker(latlng, { icon: portalDivIcon(), zIndexOffset: 200 });
    },
    onEachFeature(feature, lyr) {
      const p = feature.properties as CmPortalProyectoProps;
      bindMapHoverPopup(lyr, portalProyectoPopupHtml(p), { maxWidth: 300 });
    },
  });
}

export function PortalProyectosClusterLayer({
  geojson,
  visible,
}: {
  geojson: CmPortalGeoJson<CmPortalProyectoProps> | null;
  visible: boolean;
}) {
  const map = useMap();
  const clusterRef = useRef<L.LayerGroup | null>(null);
  const geojsonRef = useRef(geojson);
  geojsonRef.current = geojson;

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

  useEffect(() => {
    const cluster = clusterRef.current;
    const data = geojsonRef.current;
    if (!cluster || !visible || !data?.features?.length) return;

    const refresh = () => {
      cluster.clearLayers();
      const bounds = boundsFromLeaflet(map.getBounds());
      const feats = filterPointFeaturesInView(data.features, bounds);
      if (!feats.length) return;
      const layer = buildMarkersLayer({ ...data, features: feats });
      layer.eachLayer((lyr) => cluster.addLayer(lyr));
    };

    refresh();
    map.on("moveend", refresh);
    map.on("zoomend", refresh);
    return () => {
      map.off("moveend", refresh);
      map.off("zoomend", refresh);
    };
  }, [map, visible, geojson]);

  return null;
}
