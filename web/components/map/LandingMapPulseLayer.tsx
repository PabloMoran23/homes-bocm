"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { PathOptions } from "leaflet";
import {
  featureLayerStyle,
  featurePointStyle,
  type SectorFeatureCollection,
} from "@/lib/sector-geo";

const HIDDEN_STYLE: PathOptions = {
  opacity: 0,
  fillOpacity: 0,
  weight: 0,
  stroke: false,
  fill: false,
};

const HOLD_MS = 1200;
const GLOW_FADE_MS = 320;
/** Cuántas áreas aparecen en cada pulso. */
const REVEAL_BATCH_SIZE = 1;
/** Pausa entre cada pulso. */
const REVEAL_GAP_MS = 50;
/** Pausa con el mapa completo antes de reiniciar. */
const COMPLETE_HOLD_MS = 2400;

type IndexedLayer = {
  layer: L.Layer;
  feature: GeoJSON.Feature;
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

/** visibility 0–1; glow 0–1 pico de brillo en mitad de la transición. */
function lightenColor(color: string | undefined, amount: number): string | undefined {
  if (!color?.startsWith("#") || color.length < 7) return color;
  const r = Number.parseInt(color.slice(1, 3), 16);
  const g = Number.parseInt(color.slice(3, 5), 16);
  const b = Number.parseInt(color.slice(5, 7), 16);
  const mix = (c: number) => Math.round(c + (255 - c) * amount);
  const hex = (c: number) => c.toString(16).padStart(2, "0");
  return `#${hex(mix(r))}${hex(mix(g))}${hex(mix(b))}`;
}

function styleWithGlow(feature: GeoJSON.Feature, visibility: number, glow: number): PathOptions {
  const base = baseStyleForFeature(feature);
  const baseFill = Number(base.fillOpacity) || 0.28;
  const vis = Math.min(1, visibility);
  const overshoot = Math.max(0, visibility - 1);
  const glowBoost = 1 + glow * 3.2;
  const fillOpacity = Math.min(0.95, baseFill * vis * glowBoost);
  const opacity = Math.min(1, vis * (1 + glow * 0.95));
  const weight = Math.max(1.5, (Number(base.weight) || 2) + glow * 6 + overshoot * 4);

  return {
    ...base,
    stroke: true,
    fill: true,
    color: lightenColor(String(base.color || ""), glow * 0.5),
    fillColor: lightenColor(String(base.fillColor || ""), glow * 0.72),
    opacity,
    fillOpacity,
    weight,
  };
}

function applyLayerStyle(entry: IndexedLayer, visibility: number, glow = 0) {
  if (!("setStyle" in entry.layer) || typeof entry.layer.setStyle !== "function") return;
  if (visibility <= 0.02 && glow <= 0.02) {
    entry.layer.setStyle(HIDDEN_STYLE);
    return;
  }
  entry.layer.setStyle(styleWithGlow(entry.feature, visibility, glow));
}

function shuffledOrder(pool: number[]): number[] {
  const order = [...pool];
  for (let i = order.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}

/** Brillo máximo en el centro de la transición (campana más marcada). */
function glowPeak(t: number): number {
  if (t <= 0 || t >= 1) return 0;
  return Math.pow(Math.sin(t * Math.PI), 0.45);
}

/** Entrada con ligero overshoot (pop). */
function popEase(t: number): number {
  const c1 = 2.1;
  const c3 = c1 + 1;
  return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2;
}

/** Aparecen `entering`; las ya visibles se mantienen al 100 %. */
function fadeRevealBatch(
  entries: IndexedLayer[],
  visible: Set<number>,
  entering: Set<number>,
  duration: number,
  onDone?: () => void,
) {
  const start = performance.now();
  let raf = 0;

  const tick = (now: number) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = popEase(t);
    const glow = glowPeak(t);

    entries.forEach((entry, index) => {
      if (entering.has(index)) {
        applyLayerStyle(entry, eased, glow);
      } else if (visible.has(index)) {
        applyLayerStyle(entry, 1, 0);
      } else {
        applyLayerStyle(entry, 0, 0);
      }
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

function hideAll(entries: IndexedLayer[]) {
  entries.forEach((entry) => applyLayerStyle(entry, 0, 0));
}

export function LandingMapPulseLayer({
  geojson,
  visible,
  preferCanvas = false,
}: {
  geojson: SectorFeatureCollection | null;
  visible: boolean;
  /** Debe coincidir con MapContainer: canvas tapa SVG si se mezclan renderers. */
  preferCanvas?: boolean;
}) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    const features = geojson?.features || [];
    if (!visible || features.length === 0) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const renderer = preferCanvas
      ? L.canvas({ padding: 0.5 })
      : L.svg({ padding: 0.5 });
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
          entries.push({ layer: subLayer, feature });
        },
      },
    );

    layer.addTo(map);
    layer.bringToFront();
    layerRef.current = layer;

    if (entries.length === 0) {
      return () => {
        map.removeLayer(layer);
        layerRef.current = null;
      };
    }

    const pool = entries.map((_, index) => index);
    let visibleSet = new Set<number>();
    let revealOrder: number[] = [];
    let revealIndex = 0;
    let cancelFade: (() => void) | null = null;
    let pulseTimer = 0;
    let cancelled = false;

    const showStatic = () => {
      visibleSet = new Set(pool);
      entries.forEach((entry, index) => {
        applyLayerStyle(entry, visibleSet.has(index) ? 1 : 0, 0);
      });
    };

    const startCycle = () => {
      if (cancelled) return;
      visibleSet = new Set();
      revealIndex = 0;
      revealOrder = shuffledOrder(pool);
      hideAll(entries);
      pulseTimer = window.setTimeout(revealNext, HOLD_MS);
    };

    const revealNext = () => {
      if (cancelled) return;

      if (revealIndex >= revealOrder.length) {
        pulseTimer = window.setTimeout(startCycle, COMPLETE_HOLD_MS);
        return;
      }

      const batch = revealOrder.slice(revealIndex, revealIndex + REVEAL_BATCH_SIZE);
      const entering = new Set(batch);
      cancelFade?.();
      cancelFade = fadeRevealBatch(entries, visibleSet, entering, GLOW_FADE_MS, () => {
        if (cancelled) return;
        batch.forEach((index) => visibleSet.add(index));
        revealIndex += batch.length;
        pulseTimer = window.setTimeout(revealNext, REVEAL_GAP_MS);
      });
    };

    const startAnimation = () => {
      if (cancelled) return;
      if (reducedMotion) {
        showStatic();
        return;
      }
      startCycle();
    };

    const startRaf = requestAnimationFrame(startAnimation);

    return () => {
      cancelled = true;
      cancelAnimationFrame(startRaf);
      window.clearTimeout(pulseTimer);
      cancelFade?.();
      map.removeLayer(layer);
      layerRef.current = null;
    };
  }, [map, geojson, visible, preferCanvas]);

  return null;
}
