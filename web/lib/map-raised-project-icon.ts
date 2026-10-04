import type { Geometry, Position } from "geojson";
import { SIGMA_OBRA_ICON_CONFIG, type SigmaObraIconKey } from "@/lib/sigma-classification-icon";

function glyphGroup(svg: string): string {
  return svg.replace(/^<svg([^>]*)>/, (_, attributes: string) =>
    `<g${attributes.replace(/\s(?:viewBox|width|height|xmlns)="[^"]*"/g, "")}>`
  ).replace(/<\/svg>$/, "</g>");
}

/** A screen-facing badge, stem and ground shadow, at 2x pixel density. */
export function raisedProjectIconSvg(key: SigmaObraIconKey): string {
  return raisedMapIconSvg(SIGMA_OBRA_ICON_CONFIG[key]);
}

export function raisedMapIconSvg({ bg, ring, svg }: { bg: string; ring: string; svg: string }): string {
  const glyph = `<g transform="translate(13 11) scale(.91667)">${glyphGroup(svg)}</g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="144" viewBox="0 0 48 72">
    <ellipse cx="26" cy="66" rx="12" ry="4" fill="#2a2622" opacity=".16"/>
    <path d="M24 40v24" stroke="${ring}" stroke-width="2"/>
    <ellipse cx="24" cy="65" rx="3.5" ry="2" fill="${ring}"/>
    <rect x="7" y="8" width="36" height="36" rx="9" fill="#2a2622" opacity=".18"/>
    <rect x="6" y="6" width="36" height="36" rx="9" fill="${ring}"/>
    <rect x="6" y="4" width="36" height="36" rx="9" fill="${bg}" stroke="#fff" stroke-opacity=".25"/>
    <path d="M14 5h20" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="2"/>
    ${glyph}
  </svg>`;
}

/** Approximate locations use a light circular badge, keeping richer projects prominent. */
export function approximateProjectIconSvg(key: SigmaObraIconKey): string {
  const config = SIGMA_OBRA_ICON_CONFIG[key];
  const color = key === "generico" ? "#a87939" : config.bg;
  const glyph = glyphGroup(config.svg).replace(/#fff/g, color);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="104" viewBox="0 0 40 52">
    <ellipse cx="21" cy="47" rx="8" ry="2.5" fill="#2a2622" opacity=".12"/>
    <path d="M20 32v13" stroke="${color}" stroke-opacity=".65" stroke-width="1.5"/>
    <circle cx="20" cy="21" r="15" fill="#2a2622" opacity=".1"/>
    <circle cx="20" cy="19" r="15" fill="#fffdf8" stroke="${color}" stroke-opacity=".65" stroke-width="1.5" stroke-dasharray="3 2"/>
    <g transform="translate(9 8) scale(.91667)">${glyph}</g>
    <circle cx="32" cy="7" r="4" fill="#d9952d" stroke="#fffdf8" stroke-width="1.5"/>
  </svg>`;
}

/** An interior anchor: scan the rings instead of placing badges in polygon holes. */
export function projectIconAnchor(geometry: Geometry): [number, number] | null {
  if (geometry.type === "Point") {
    const [lng, lat] = geometry.coordinates;
    return Number.isFinite(lng) && Number.isFinite(lat) ? [lng, lat] : null;
  }
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.type === "MultiPolygon" ? geometry.coordinates : [];
  let best: { point: [number, number]; area: number } | null = null;
  for (const rings of polygons) {
    const outer = rings[0];
    if (!outer?.length) continue;
    const xs = outer.map(p => p[0]);
    const ys = outer.map(p => p[1]);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const area = (Math.max(...xs) - Math.min(...xs)) * (maxY - minY);
    if (!Number.isFinite(area) || area <= 0 || (best && area <= best.area)) continue;
    let candidate: [number, number] | null = null;
    let longest = 0;
    for (const ratio of [0.5, 0.35, 0.65]) {
      const y = minY + (maxY - minY) * ratio;
      const intersections: number[] = [];
      for (const ring of rings) {
        for (let i = 0; i < ring.length; i++) {
          const a: Position = ring[i], b: Position = ring[(i + 1) % ring.length];
          if ((a[1] > y) !== (b[1] > y)) intersections.push(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]));
        }
      }
      intersections.sort((a, b) => a - b);
      for (let i = 0; i + 1 < intersections.length; i += 2) {
        const width = intersections[i + 1] - intersections[i];
        if (width > longest) { longest = width; candidate = [(intersections[i] + intersections[i + 1]) / 2, y]; }
      }
    }
    if (candidate) best = { point: candidate, area };
  }
  return best?.point ?? null;
}
