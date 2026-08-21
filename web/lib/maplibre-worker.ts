import { setWorkerUrl } from "maplibre-gl";

let ready = false;

/**
 * Turbopack no emite el worker junto a maplibre-gl-shared; sin esto el mapa
 * monta el fondo y no pide teselas.
 */
export function ensureMaplibreWorker() {
  if (ready || typeof window === "undefined") return;
  setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
  ready = true;
}
