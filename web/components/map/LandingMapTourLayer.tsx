"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { PathOptions } from "leaflet";
import type { LandingMapSpotlightItem } from "@/lib/landing-map-spotlight";
import type { LandingTourActiveChange } from "@/lib/landing-map-tour";
import {
  estimatePlacementForBounds,
  fitBoundsPaddingForPlacement,
  placementFromLatLng,
  type MapSpotlightPlacement,
} from "@/lib/map-spotlight-placement";
import {
  featureLayerStyle,
  featurePointStyle,
  type SectorFeatureCollection,
} from "@/lib/sector-geo";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { capZoomForContainer } from "@/lib/map-visual-scale";
import { HomesFocusMask } from "@/components/map/homes-focus-mask-layer";
import { isPolygonFeature } from "@/lib/map-focus-mask";

const HIDDEN_STYLE: PathOptions = {
  opacity: 0,
  fillOpacity: 0,
  weight: 0,
  stroke: false,
  fill: false,
};

const FLY_DURATION_S = 1.35;
const CARD_DELAY_MS = 450;
const HOLD_MS = 4200;
const FADE_MS = 380;
const BETWEEN_MS = 280;

type IndexedLayer = {
  layer: L.Layer;
  feature: GeoJSON.Feature;
  grupo: string;
};

function baseStyleForFeature(feature: GeoJSON.Feature): PathOptions {
  const props = feature.properties as Record<string, unknown> | undefined;
  const geom = feature.geometry;
  return (
    geom?.type === "Point"
      ? (featurePointStyle(props, null) as PathOptions)
      : (featureLayerStyle(props, null) as PathOptions)
  );
}

const FOCUS_OUTLINE: PathOptions = {
  color: "#2a2622",
  weight: 0,
  dashArray: "7 5",
  fill: true,
  fillColor: "#d4923a",
  fillOpacity: 0.01,
  opacity: 0,
  stroke: false,
};

function styleWithVisibility(feature: GeoJSON.Feature, visibility: number, active: boolean): PathOptions {
  const vis = Math.min(1, Math.max(0, visibility));
  if (!active || vis <= 0.02) return HIDDEN_STYLE;
  if (!isPolygonFeature(feature)) {
    const base = baseStyleForFeature(feature);
    return {
      ...base,
      opacity: vis,
      fillOpacity: (Number(base.fillOpacity) || 0.5) * vis,
    };
  }
  return {
    ...FOCUS_OUTLINE,
    fillOpacity: 0.01 * vis,
  };
}

function applyLayerStyle(entry: IndexedLayer, visibility: number, active: boolean) {
  if (!("setStyle" in entry.layer) || typeof entry.layer.setStyle !== "function") return;
  if (visibility <= 0.02) {
    entry.layer.setStyle(HIDDEN_STYLE);
    return;
  }
  entry.layer.setStyle(styleWithVisibility(entry.feature, visibility, active));
}

function popEase(t: number): number {
  const c1 = 2.1;
  const c3 = c1 + 1;
  return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2;
}

function fadeLayers(
  entries: IndexedLayer[],
  activeGrupo: string,
  duration: number,
  onDone?: () => void,
) {
  const start = performance.now();
  let raf = 0;

  const tick = (now: number) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = popEase(t);

    entries.forEach((entry) => {
      const active = entry.grupo === activeGrupo;
      applyLayerStyle(entry, active ? eased : 0, active);
    });

    if (t < 1) {
      raf = requestAnimationFrame(tick);
    } else {
      onDone?.();
    }
  };

  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}

function featuresForGrupo(entries: IndexedLayer[], grupo: string): GeoJSON.Feature[] {
  const key = expedienteGrupoKeyFromVariant(grupo);
  return entries.filter((e) => e.grupo === key).map((e) => e.feature);
}

function hideAll(entries: IndexedLayer[]) {
  entries.forEach((entry) => applyLayerStyle(entry, 0, false));
}

function shuffledOrder(length: number): number[] {
  const order = Array.from({ length }, (_, i) => i);
  for (let i = order.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}

function flyToBounds(
  map: L.Map,
  bounds: L.LatLngBounds,
  opts: L.FitBoundsOptions,
): Promise<void> {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      map.off("moveend", finish);
      resolve();
    };
    map.once("moveend", finish);
    map.flyToBounds(bounds, opts);
    window.setTimeout(finish, (opts.duration ?? FLY_DURATION_S) * 1000 + 200);
  });
}

function wait(ms: number, cancelled: () => boolean): Promise<void> {
  return new Promise((resolve) => {
    const t = window.setTimeout(() => {
      if (!cancelled()) resolve();
    }, ms);
    if (cancelled()) {
      window.clearTimeout(t);
      resolve();
    }
  });
}

function flyToBoundsWithPlacement(
  map: L.Map,
  bounds: L.LatLngBounds,
  center: [number, number],
  maxZoom: number,
): Promise<MapSpotlightPlacement> {
  const placement = estimatePlacementForBounds(map, bounds, center);
  const pad = fitBoundsPaddingForPlacement(placement);

  return flyToBounds(map, bounds, {
    paddingTopLeft: L.point(pad.left, pad.top),
    paddingBottomRight: L.point(pad.right, pad.bottom),
    maxZoom,
    duration: FLY_DURATION_S,
    easeLinearity: 0.22,
  }).then(() => placementFromLatLng(map, center));
}

export function LandingMapTourLayer({
  geojson,
  items,
  visible,
  onActiveChange,
  preferCanvas = false,
}: {
  geojson: SectorFeatureCollection | null;
  items: LandingMapSpotlightItem[];
  visible: boolean;
  onActiveChange: (change: LandingTourActiveChange) => void;
  preferCanvas?: boolean;
}) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);
  const onActiveChangeRef = useRef(onActiveChange);
  onActiveChangeRef.current = onActiveChange;

  useEffect(() => {
    const features = geojson?.features || [];
    if (!visible || features.length === 0 || items.length === 0) {
      onActiveChangeRef.current({ item: null, placement: null });
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const renderer = preferCanvas ? L.canvas({ padding: 0.5 }) : L.svg({ padding: 0.5 });
    const entries: IndexedLayer[] = [];

    const layer = L.geoJSON(
      { type: "FeatureCollection", features } as GeoJSON.FeatureCollection,
      {
        ...(renderer ? { renderer } : {}),
        style() {
          return HIDDEN_STYLE;
        },
        pointToLayer(_feature, latlng) {
          return L.circleMarker(latlng, HIDDEN_STYLE);
        },
        onEachFeature(feature, subLayer) {
          const props = feature.properties as Record<string, unknown> | undefined;
          const grupo = expedienteGrupoKeyFromVariant(
            String(props?.expedienteGrupo || props?.EXP_TX_NUMERO || ""),
          );
          entries.push({ layer: subLayer, feature, grupo });
        },
      },
    );

    layer.addTo(map);
    layer.bringToFront();
    layerRef.current = layer;

    const mask = new HomesFocusMask();
    mask.addTo(map);

    let cancelled = false;
    let cancelFade: (() => void) | null = null;
    let stepTimer = 0;

    const isCancelled = () => cancelled;

    const showStatic = (item: LandingMapSpotlightItem) => {
      const [s, w, n, e] = item.bounds;
      const bounds = L.latLngBounds([s, w], [n, e]);
      const el = map.getContainer();
      const maxZoom = capZoomForContainer(15, el?.clientWidth ?? 400, el?.clientHeight ?? 300);
      const pad = fitBoundsPaddingForPlacement(
        estimatePlacementForBounds(map, bounds, item.center),
      );
      map.fitBounds(bounds, {
        paddingTopLeft: L.point(pad.left, pad.top),
        paddingBottomRight: L.point(pad.right, pad.bottom),
        maxZoom,
        animate: false,
      });
      const placement = placementFromLatLng(map, item.center);
      cancelFade?.();
      const feat = featuresForGrupo(entries, item.expedienteGrupo).filter(isPolygonFeature);
      if (feat.length) {
        mask.setFeatures(feat);
        mask.animateProgress(1, FADE_MS);
      }
      cancelFade = fadeLayers(
        entries,
        expedienteGrupoKeyFromVariant(item.expedienteGrupo),
        FADE_MS,
        () => {
          onActiveChangeRef.current({ item, placement });
        },
      );
    };

    const runTour = async () => {
      const order = shuffledOrder(items.length);
      let step = 0;

      while (!cancelled) {
        const item = items[order[step]!];
        if (!item) break;

        onActiveChangeRef.current({ item: null, placement: null });
        hideAll(entries);
        mask.animateProgress(0, 220);

        const [s, w, n, e] = item.bounds;
        const bounds = L.latLngBounds([s, w], [n, e]);
        const el = map.getContainer();
        const maxZoom = capZoomForContainer(15, el?.clientWidth ?? 400, el?.clientHeight ?? 300);

        const placement = await flyToBoundsWithPlacement(map, bounds, item.center, maxZoom);
        if (cancelled) break;

        const feat = featuresForGrupo(entries, item.expedienteGrupo).filter(isPolygonFeature);
        if (feat.length) {
          mask.setFeatures(feat);
          mask.animateProgress(1, 520);
        }

        await wait(CARD_DELAY_MS, isCancelled);
        if (cancelled) break;

        cancelFade?.();
        await new Promise<void>((resolve) => {
          cancelFade = fadeLayers(
            entries,
            expedienteGrupoKeyFromVariant(item.expedienteGrupo),
            FADE_MS,
            () => {
              onActiveChangeRef.current({ item, placement });
              resolve();
            },
          );
        });
        if (cancelled) break;

        await wait(HOLD_MS, isCancelled);
        if (cancelled) break;

        onActiveChangeRef.current({ item: null, placement: null });
        hideAll(entries);
        mask.animateProgress(0, 280);

        await wait(BETWEEN_MS, isCancelled);
        if (cancelled) break;

        step = (step + 1) % order.length;
      }
    };

    const start = () => {
      if (cancelled) return;
      if (reducedMotion) {
        void showStatic(items[0]!);
        return;
      }
      void runTour();
    };

    stepTimer = window.setTimeout(start, 400);

    return () => {
      cancelled = true;
      window.clearTimeout(stepTimer);
      cancelFade?.();
      mask.animateProgress(0, 1);
      map.removeLayer(mask);
      onActiveChangeRef.current({ item: null, placement: null });
      map.removeLayer(layer);
      layerRef.current = null;
    };
  }, [map, geojson, items, visible, preferCanvas]);

  return null;
}
