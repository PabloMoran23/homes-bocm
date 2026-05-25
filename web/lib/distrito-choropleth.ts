import { PORTAL_TEAL } from "@/lib/dashboard-chart-theme";

/** Gris (sin datos) → verdes/teal del portal (bajo → alto). */
export const DISTRITO_HEAT_PALETTE = [
  { fill: "#f1f5f9", stroke: "#94a3b8" },
  { fill: "#ecfdf5", stroke: "#99f6e4" },
  { fill: "#ccfbf1", stroke: "#5eead4" },
  { fill: "#99f6e4", stroke: "#2dd4bf" },
  { fill: "#5eead4", stroke: "#14b8a6" },
  { fill: "#2dd4bf", stroke: "#0f766e" },
  { fill: "#14b8a6", stroke: "#0f766e" },
  { fill: "#0f766e", stroke: "#134e4a" },
] as const;

export type MadridDistritoGeoProperties = {
  cod_dis: string | null;
  nombre: string;
  distrito_key: string;
};

/** Umbrales por cuantiles (solo valores > 0). */
export function distritoQuantileBreaks(counts: number[], buckets = 5): number[] {
  const sorted = counts.filter((c) => c > 0).sort((a, b) => a - b);
  if (!sorted.length) return [];
  const breaks: number[] = [];
  for (let i = 1; i < buckets; i++) {
    const idx = Math.min(
      sorted.length - 1,
      Math.max(0, Math.floor((i / buckets) * sorted.length) - 1),
    );
    const v = sorted[idx];
    if (breaks.length === 0 || v > breaks[breaks.length - 1]) breaks.push(v);
  }
  return breaks;
}

/** Índice 0 = sin datos; 1…n = tramos de la paleta. */
export function distritoColorIndex(count: number, breaks: number[]): number {
  if (count <= 0) return 0;
  const paletteSteps = DISTRITO_HEAT_PALETTE.length - 1;
  if (!breaks.length) {
    return Math.min(paletteSteps, 1);
  }
  let bucket = 1;
  for (const b of breaks) {
    if (count >= b) bucket += 1;
  }
  return Math.min(paletteSteps, bucket);
}

export function distritoPaletteEntry(index: number) {
  return DISTRITO_HEAT_PALETTE[Math.min(index, DISTRITO_HEAT_PALETTE.length - 1)];
}

export function distritoFillColor(count: number, breaks: number[]): string {
  return distritoPaletteEntry(distritoColorIndex(count, breaks)).fill;
}

export function distritoStrokeColor(count: number, breaks: number[]): string {
  return distritoPaletteEntry(distritoColorIndex(count, breaks)).stroke;
}

/** Gradiente CSS para la leyenda (gris → teal portal). */
export function distritoLegendGradient(): string {
  return `linear-gradient(to right, ${DISTRITO_HEAT_PALETTE[0].fill} 0%, ${DISTRITO_HEAT_PALETTE[3].fill} 45%, ${PORTAL_TEAL} 100%)`;
}
