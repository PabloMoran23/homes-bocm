import L from "leaflet";
import {
  normalizarActuacionEdificio,
  type ActuacionEdificioInput,
} from "@/lib/actuacion-edificio";
import {
  clasificarLicenciaMapa,
  licenciaTituloDesdeTipo,
  type LicenciaMapaCategoria,
} from "@/lib/licencia-tipos";
import { LICENCIA_MAPA_CONFIG, LICENCIA_MAPA_LEYENDA } from "@/lib/licencia-mapa-config";
import { SIGMA_MAP_POINT } from "@/lib/map-sigma-colors";

export type { LicenciaMapaCategoria };
export { clasificarLicenciaMapa, licenciaTituloDesdeTipo };
export { LICENCIA_MAPA_CONFIG, LICENCIA_MAPA_LEYENDA };

export function createLicenciaDivIcon(
  categoria: LicenciaMapaCategoria,
  highlighted = false,
  size: "sm" | "md" = "md",
): L.DivIcon {
  const cfg = LICENCIA_MAPA_CONFIG[categoria];
  const sizePx =
    size === "sm" ? (highlighted ? 24 : 20) : highlighted ? 32 : 26;
  const border = highlighted ? "3px solid #0f766e" : `2px solid ${cfg.ring}`;
  const svg =
    size === "sm"
      ? cfg.svg.replace(/width="14"/g, 'width="11"').replace(/width="10"/g, 'width="8"')
      : cfg.svg;
  return L.divIcon({
    className: "homes-licencia-marker",
    html: `<div style="width:${sizePx}px;height:${sizePx}px;background:${cfg.bg};border:${border};border-radius:50%;box-shadow:0 2px 6px rgba(15,23,42,0.25);display:flex;align-items:center;justify-content:center;box-sizing:border-box">${svg}</div>`,
    iconSize: [sizePx, sizePx],
    iconAnchor: [sizePx / 2, sizePx / 2],
    popupAnchor: [0, -sizePx / 2],
  });
}

const CENTRO_SVG = `<svg width="12" height="12" viewBox="0 0 24 24" fill="#fff"><circle cx="12" cy="12" r="4"/></svg>`;

export function createCentroBusquedaDivIcon(): L.DivIcon {
  const sizePx = 28;
  return L.divIcon({
    className: "homes-licencia-marker",
    html: `<div style="width:${sizePx}px;height:${sizePx}px;background:#0f766e;border:3px solid #fff;border-radius:50%;box-shadow:0 2px 8px rgba(15,118,110,0.45);display:flex;align-items:center;justify-content:center">${CENTRO_SVG}</div>`,
    iconSize: [sizePx, sizePx],
    iconAnchor: [sizePx / 2, sizePx / 2],
    popupAnchor: [0, -sizePx / 2],
  });
}

export function createSigmaDivIcon(size: "sm" | "md" = "md"): L.DivIcon {
  const sizePx = size === "sm" ? 20 : 24;
  const sigma = SIGMA_MAP_POINT.default;
  return L.divIcon({
    className: "homes-licencia-marker",
    html: `<div style="width:${sizePx}px;height:${sizePx}px;background:${sigma.fillColor};border:2px solid ${sigma.color};border-radius:50%;box-shadow:0 2px 5px rgba(79,70,229,0.35);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff">Σ</div>`,
    iconSize: [sizePx, sizePx],
    iconAnchor: [sizePx / 2, sizePx / 2],
    popupAnchor: [0, -sizePx / 2],
  });
}

export function clasificarLicenciaMapaDesdeActuacion(
  input: ActuacionEdificioInput | string | null | undefined,
): LicenciaMapaCategoria {
  if (input == null || typeof input === "string") {
    return clasificarLicenciaMapa(input);
  }
  return normalizarActuacionEdificio(input).mapaCategoria;
}

export function createLicenciaMapMarker(
  latlng: L.LatLngExpression,
  actuacion: ActuacionEdificioInput | string | null | undefined,
  options?: { highlighted?: boolean },
): L.Marker {
  const cat = clasificarLicenciaMapaDesdeActuacion(actuacion);
  return L.marker(latlng, {
    icon: createLicenciaDivIcon(cat, options?.highlighted),
  });
}

export function licenciaMapTooltipLabel(
  actuacion: ActuacionEdificioInput | string | null | undefined,
  direccion?: string | null,
): string {
  const titulo =
    actuacion != null && typeof actuacion !== "string"
      ? normalizarActuacionEdificio(actuacion).etiqueta
      : licenciaTituloDesdeTipo(actuacion);
  return [direccion, titulo].filter(Boolean).join(" · ") || titulo;
}
