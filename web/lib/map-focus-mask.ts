import type { Feature, Position } from "geojson";

export const FOCUS_MASK_PANE = "homesFocusMask";
/** Por encima de polígonos y markers; por debajo de popups y controles. */
export const FOCUS_MASK_PANE_Z = "560";

export const FOCUS_VEIL_COLOR = "243, 238, 228";
export const FOCUS_VEIL_ALPHA = 0.86;
export const FOCUS_FEATHER_PX = 28;
export const FOCUS_BOUNDARY_COLOR = "#2a2622";
export const FOCUS_BOUNDARY_ACCENT = "#9a5c48";

export function isPolygonFeature(feature: Feature | undefined | null): boolean {
  const t = feature?.geometry?.type;
  return t === "Polygon" || t === "MultiPolygon";
}

export function polygonFeaturesOf(
  features: Feature[] | null | undefined,
): Feature[] {
  return (features ?? []).filter(isPolygonFeature);
}

export function focusKeyForFeatures(features: Feature[]): string {
  return features
    .map((f) => {
      const p = (f.properties ?? {}) as Record<string, unknown>;
      return String(
        p.expedienteGrupo || p.EXP_TX_NUMERO || p.stable_key || f.id || f.geometry?.type || "",
      );
    })
    .join("|");
}

function ringToLatLngs(ring: Position[]): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (const pos of ring) {
    const lng = pos[0];
    const lat = pos[1];
    if (typeof lng === "number" && typeof lat === "number") {
      out.push([lat, lng]);
    }
  }
  return out;
}

/** Anillos [lat, lng] por polígono (exterior + huecos). */
export function featurePolygonRings(feature: Feature): Array<Array<[number, number]>>[] {
  const geom = feature.geometry;
  if (!geom) return [];
  if (geom.type === "Polygon") {
    return [geom.coordinates.map(ringToLatLngs).filter((r) => r.length >= 3)];
  }
  if (geom.type === "MultiPolygon") {
    return geom.coordinates
      .map((poly) => poly.map(ringToLatLngs).filter((r) => r.length >= 3))
      .filter((poly) => poly.length > 0 && poly[0]!.length >= 3);
  }
  return [];
}
