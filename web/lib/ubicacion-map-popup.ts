import { actuacionDesdeMapProps, ubicacionPath, type UbicacionMapProperties } from "@/lib/ubicacion";
import { normalizarActuacionEdificio } from "@/lib/actuacion-edificio";
import { licenciaTituloDesdeTipo } from "@/lib/licencia-tipos";
import {
  escapeMapPopupHtml,
  mapPopupLinkHtml,
  mapPopupMetaLine,
} from "@/lib/map-popup-html";

function formatFecha(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = iso.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return iso;
  const [y, m, day] = d.split("-");
  return `${Number(day)}/${Number(m)}/${y}`;
}

export function ubicacionMapPopupHtml(p: UbicacionMapProperties): string {
  const bits: string[] = [];
  const titulo = p.direccion?.trim() || "Edificio en Madrid";
  bits.push(`<div style="font-weight:700;font-size:14px;color:#0f172a">${escapeMapPopupHtml(titulo)}</div>`);

  const actuacion = normalizarActuacionEdificio(actuacionDesdeMapProps(p));
  const actuacionLabel = p.actuacionQueLabel?.trim() || actuacion.etiqueta;
  if (actuacionLabel) {
    bits.push(
      `<div style="margin-top:6px;font-size:13px;color:#334155">${escapeMapPopupHtml(actuacionLabel)}</div>`,
    );
  } else if (p.ultimaLicenciaTipo) {
    bits.push(
      `<div style="margin-top:6px;font-size:13px;color:#334155">${escapeMapPopupHtml(licenciaTituloDesdeTipo(p.ultimaLicenciaTipo))}</div>`,
    );
  }

  const lugar = [p.distrito, p.barrio].filter(Boolean).join(" · ");
  if (lugar) bits.push(mapPopupMetaLine("Zona", lugar));

  const fecha = formatFecha(p.ultimaLicenciaFecha);
  if (fecha) bits.push(mapPopupMetaLine("Última licencia", fecha));

  if (p.ultimaLicenciaUso?.trim()) {
    bits.push(mapPopupMetaLine("Uso", p.ultimaLicenciaUso.trim()));
  }

  const stats: string[] = [];
  if (p.licencias > 0) {
    stats.push(
      `${p.licencias.toLocaleString("es-ES")} licencia${p.licencias === 1 ? "" : "s"}`,
    );
  }
  if (p.sigma > 0) {
    stats.push(`${p.sigma.toLocaleString("es-ES")} plan${p.sigma === 1 ? "" : "es"}`);
  }
  if (stats.length) {
    bits.push(
      `<div style="margin-top:6px;font-size:11px;color:#64748b">${escapeMapPopupHtml(stats.join(" · "))}</div>`,
    );
  }

  bits.push(
    `<div style="margin-top:6px;font-size:11px;color:#047857">Obra o actuación autorizada (datos abiertos Ayto.)</div>`,
  );
  bits.push(mapPopupLinkHtml(ubicacionPath(p.ndp), "Más información"));

  return bits.join("");
}
