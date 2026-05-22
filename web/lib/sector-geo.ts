/** GeoJSON para sector_geometry o capas SIGMA (Ayto. Madrid). */

import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import {
  generaViviendaUserLabel,
  sigmaMapPopupLayerHint,
  sigmaTipoActuacion,
} from "@/lib/sigma-user-labels";
import { licenciaTituloDesdeTipo } from "@/lib/ubicacion-resumen";
import { SIGMA_MAP_POINT, SIGMA_MAP_POLYGON } from "@/lib/map-sigma-colors";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";

export type SectorFeatureProperties = {
  stable_key?: string;
  municipio?: string;
  sector?: string;
  boletin_source_id?: string | null;
  resolver_id?: string | null;
  DS_NOMB_AMB?: string | null;
  geometry_scope?: string | null;
  /** SIGMA información pública / tramitados */
  EXP_TX_NUMERO?: string | null;
  EXP_TX_DENOM?: string | null;
  FAS_TX_DENOM?: string | null;
  FIG_TX_ETIQ?: string | null;
  TFIG_TX_ABREV?: string | null;
  ORG_TX_DESC?: string | null;
  Enlace?: string | null;
  ENLACE?: string | null;
  sigma_layer_kind?: string | null;
  sigma_layer_id?: number | null;
  /** Licencias urbanísticas (datos abiertos 300193) */
  licencia_urbana?: boolean;
  fecha_concesion?: string | null;
  tipo_expediente?: string | null;
  uso?: string | null;
  distrito?: string | null;
  direccion?: string | null;
  procedimiento?: string | null;
  anio_dataset?: number | null;
};

/** Entradas BOCM enlazadas al mismo expediente (popup mapa SIGMA). */
export type SigmaBocmPopupLink = {
  id: string;
  title: string;
  bocmDate: string;
  artNum?: string | null;
  esRelevante?: boolean | null;
};

export type SigmaMetricsPopupSlice = {
  num_viviendas_max?: number | null;
  genera_vivienda_nueva?: string | null;
};

export type FeaturePopupOptions = {
  sigmaBocmByExpediente?: Readonly<Record<string, readonly SigmaBocmPopupLink[]>> | null;
  sigmaMetricsByExpediente?: Readonly<Record<string, SigmaMetricsPopupSlice>> | null;
};

function propsRecord(p: SectorFeatureProperties | undefined): Record<string, unknown> {
  return (p || {}) as Record<string, unknown>;
}

export function isLicenciaFeature(p: SectorFeatureProperties | undefined): boolean {
  return propsRecord(p).licencia_urbana === true;
}

export function isSigmaFeature(p: SectorFeatureProperties | undefined): boolean {
  const r = propsRecord(p);
  return Boolean(r.EXP_TX_NUMERO || r.EXP_TX_DENOM || r.sigma_layer_kind);
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s: string): string {
  return escapeHtml(s).replace(/'/g, "&#39;");
}

export function featurePopupHtml(
  p: SectorFeatureProperties | undefined,
  opts?: FeaturePopupOptions,
): string {
  const r = propsRecord(p);
  if (isLicenciaFeature(p)) {
    const bits: string[] = [];
    if (r.direccion) bits.push(`<b>${escapeHtml(String(r.direccion))}</b>`);
    if (r.tipo_expediente) {
      bits.push(
        `<div class="text-xs text-slate-700">${escapeHtml(licenciaTituloDesdeTipo(String(r.tipo_expediente)))}</div>`,
      );
    }
    if (r.uso) bits.push(`<div><i>Uso:</i> ${escapeHtml(String(r.uso))}</div>`);
    if (r.distrito) bits.push(`<div><i>Distrito:</i> ${escapeHtml(String(r.distrito))}</div>`);
    if (r.fecha_concesion) {
      bits.push(`<div><i>Concesión:</i> ${escapeHtml(String(r.fecha_concesion))}</div>`);
    }
    if (r.procedimiento) {
      bits.push(`<div class="text-xs text-slate-500">${escapeHtml(String(r.procedimiento).slice(0, 100))}</div>`);
    }
    bits.push(
      `<div style="color:#047857;font-size:11px">Obra o actuación autorizada (datos abiertos Ayto.)</div>`,
    );
    return bits.join("<br/>");
  }
  if (isSigmaFeature(p)) {
    const denom = String(r.EXP_TX_DENOM || "Proyecto urbanístico").trim();
    const bits: string[] = [`<b>${escapeHtml(denom)}</b>`];
    const tipo = sigmaTipoActuacion(
      r.FIG_TX_ETIQ ? String(r.FIG_TX_ETIQ) : null,
      r.TFIG_TX_ABREV ? String(r.TFIG_TX_ABREV) : null,
    );
    if (tipo) {
      bits.push(`<div class="text-xs text-slate-600">${escapeHtml(tipo)}</div>`);
    }
    if (r.FAS_TX_DENOM) {
      bits.push(`<div><i>Estado:</i> ${escapeHtml(String(r.FAS_TX_DENOM))}</div>`);
    }
    if (r.ORG_TX_DESC) {
      bits.push(
        `<div><i>Tramita:</i> ${escapeHtml(String(r.ORG_TX_DESC).slice(0, 120))}</div>`,
      );
    }
    const layerHint = sigmaMapPopupLayerHint(
      r.sigma_layer_kind ? String(r.sigma_layer_kind) : null,
    );
    if (layerHint) {
      bits.push(`<div style="color:#0369a1;font-size:11px">${escapeHtml(layerHint)}</div>`);
    }
    if (r.EXP_TX_NUMERO) {
      bits.push(
        `<div class="text-[10px] text-slate-400">Ref. ${escapeHtml(String(r.EXP_TX_NUMERO))}</div>`,
      );
    }
    const visorUrl = r.Enlace || r.ENLACE;
    const expKey = expedienteGrupoKeyFromVariant(String(r.EXP_TX_NUMERO || ""));
    const metricSlice = expKey ? opts?.sigmaMetricsByExpediente?.[expKey] : undefined;
    if (metricSlice?.num_viviendas_max != null) {
      bits.push(
        `<div style="margin-top:6px;padding:6px 8px;background:#f0fdfa;border-radius:8px;font-size:12px;color:#115e59">` +
          `<strong>Hasta ${escapeHtml(String(metricSlice.num_viviendas_max.toLocaleString("es-ES")))} viviendas</strong>` +
          `<span style="color:#64748b;font-weight:400"> · estimación Homes</span></div>`,
      );
    } else if (metricSlice?.genera_vivienda_nueva && metricSlice.genera_vivienda_nueva !== "desconocido") {
      bits.push(
        `<div style="margin-top:6px;font-size:11px;color:#64748b">${escapeHtml(generaViviendaUserLabel(metricSlice.genera_vivienda_nueva))}</div>`,
      );
    }
    if (expKey) {
      const fichaRel = sigmaFichaPath(expKey);
      bits.push(
        `<a href="${escapeAttr(fichaRel)}" style="display:inline-block;margin-top:6px;color:#0d9488;font-weight:700;font-size:13px">Ver ficha del proyecto</a>`,
      );
    }
    if (visorUrl) {
      bits.push(
        `<a href="${escapeAttr(String(visorUrl))}" target="_blank" rel="noopener noreferrer" style="color:#64748b;font-weight:600;font-size:12px">Visor municipal ↗</a>`,
      );
    }

    const rawHits = expKey ? opts?.sigmaBocmByExpediente?.[expKey] : undefined;
    const bocmHits: SigmaBocmPopupLink[] = Array.isArray(rawHits)
      ? rawHits.filter((x): x is SigmaBocmPopupLink => typeof x === "object" && x !== null && "id" in x)
      : [];
    if (bocmHits?.length) {
      bits.push(
        `<hr style="margin:8px 0;border:none;border-top:1px solid #e2e8f0"/>` +
          `<div style="font-weight:600;color:#334155;font-size:11px;text-transform:uppercase;letter-spacing:0.04em">Anuncios en el Boletín</div>`,
      );
      for (const h of bocmHits.slice(0, 6)) {
        const rel = `/proyecto/${encodeURIComponent(h.id)}`;
        const relTag = h.esRelevante === true ? " · relevante" : "";
        const art = h.artNum ? ` · art. ${escapeHtml(h.artNum)}` : "";
        bits.push(
          `<div style="margin-top:6px;line-height:1.35">` +
            `<a href="${escapeAttr(rel)}" style="color:#0d9488;font-weight:600;font-size:13px">Ver anuncio</a>` +
            `<div style="font-size:11px;color:#64748b;margin-top:2px">${escapeHtml(h.bocmDate)}${art}${relTag}</div>` +
            `<div style="font-size:11px;color:#334155;margin-top:2px">${escapeHtml((h.title || "").slice(0, 140))}${(h.title || "").length > 140 ? "…" : ""}</div>` +
            `</div>`,
        );
      }
      if (bocmHits.length > 6) {
        bits.push(
          `<div style="font-size:10px;color:#94a3b8;margin-top:4px">+${bocmHits.length - 6} anuncios más con este expediente</div>`,
        );
      }
    }

    return bits.join("<br/>");
  }

  const bits = [
    `<b>${escapeHtml(String(r.municipio || "?"))}</b>`,
    r.sector ? `<div>${escapeHtml(String(r.sector).slice(0, 180))}</div>` : "",
    r.DS_NOMB_AMB ? `<div><i>Ámbito SIT:</i> ${escapeHtml(String(r.DS_NOMB_AMB))}</div>` : "",
    typeof r.resolver_id === "string" && r.resolver_id.startsWith("cm_sitcm")
      ? "<div style='color:#1d4ed8'>Polígono planeamiento (CM)</div>"
      : r.resolver_id
        ? "<div style='color:#64748b'>Geometría del sector</div>"
        : "",
  ].filter(Boolean);
  return bits.join("<br/>");
}

export function featureLayerStyle(
  p: SectorFeatureProperties | undefined,
): Record<string, unknown> {
  if (isLicenciaFeature(p)) {
    return { color: "#047857", weight: 1.5, fillColor: "#10b981", fillOpacity: 0.62 };
  }
  if (isSigmaFeature(p)) {
    const kind = String(propsRecord(p).sigma_layer_kind || "");
    if (kind === "tramitados_ad") return SIGMA_MAP_POLYGON.tramitados_ad;
    if (kind === "gestion") return SIGMA_MAP_POLYGON.gestion;
    if (kind === "urbanizacion") return SIGMA_MAP_POLYGON.urbanizacion;
    return SIGMA_MAP_POLYGON.default;
  }
  return sectorLayerStyle(p?.resolver_id) as Record<string, unknown>;
}

export function featurePointStyle(p: SectorFeatureProperties | undefined): Record<string, unknown> {
  if (isLicenciaFeature(p)) {
    return { radius: 5, color: "#047857", weight: 1.5, fillColor: "#10b981", fillOpacity: 0.82 };
  }
  if (isSigmaFeature(p)) {
    if (String(propsRecord(p).sigma_layer_kind || "") === "tramitados_ad") {
      return SIGMA_MAP_POINT.tramitados_ad;
    }
    return SIGMA_MAP_POINT.default;
  }
  return sectorPointStyle(p?.resolver_id) as Record<string, unknown>;
}

export type SectorFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties?: SectorFeatureProperties;
    geometry?: { type: string; coordinates?: unknown };
  }>;
};

export function sectorLayerStyle(resolverId: string | null | undefined) {
  if (resolverId?.startsWith("madrid_ayto")) {
    return SIGMA_MAP_POLYGON.default;
  }
  const isCm = resolverId?.startsWith("cm_sitcm");
  if (isCm) {
    return SIGMA_MAP_POLYGON.gestion;
  }
  return {
    color: "#0f766e",
    weight: 1.5,
    fillColor: "#99f6e4",
    fillOpacity: 0.18,
  };
}

export function sectorPointStyle(resolverId: string | null | undefined) {
  if (resolverId?.startsWith("madrid_ayto")) {
    return SIGMA_MAP_POINT.default;
  }
  const isCm = resolverId?.startsWith("cm_sitcm");
  if (isCm) {
    return { ...SIGMA_MAP_POINT.default, radius: 7, fillColor: "#14b8a6" };
  }
  return { radius: 5, color: "#0f766e", weight: 2, fillColor: "#99f6e4", fillOpacity: 0.72 };
}
