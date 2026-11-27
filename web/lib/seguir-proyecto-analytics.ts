import { trackEvent } from "@/lib/analytics";
import { claimOnce, type SeguirPosicion, type SeguirSegmento } from "@/lib/seguir-proyecto";

const seen = new Set<string>();
let listening = false;

function watchSession() {
  if (listening || typeof window === "undefined") return;
  listening = true;
  window.addEventListener("homes-analytics-session", () => seen.clear());
}

/** Once per analytics session and placement, when the form is on screen. */
export function recordSeguirVisto(posicion: SeguirPosicion) {
  watchSession();
  if (!claimOnce(seen, `visto:${posicion}`)) return;
  trackEvent("seguir_visto", { posicion });
}

export function recordSeguirClic(posicion: SeguirPosicion) {
  watchSession();
  trackEvent("seguir_clic", { posicion });
}

export function recordSeguirAlta(posicion: SeguirPosicion, proyecto: string) {
  trackEvent("seguir_alta", { posicion, proyecto: proyecto.slice(0, 160) });
}

export function recordSeguirSegmento(valor: SeguirSegmento) {
  trackEvent("seguir_segmento", { valor });
}

export function resetSeguirAnalyticsForTests() {
  seen.clear();
}
