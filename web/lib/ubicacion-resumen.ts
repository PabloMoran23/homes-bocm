import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import type {
  UbicacionFicha,
  UbicacionLicencia,
  UbicacionSigmaExpediente,
  UbicacionTramite,
} from "@/lib/ubicacion";

export type UbicacionExpedienteCategoria = "local" | "sector" | "normativa_ciudad";

const NORMATIVA_CIUDAD_RE =
  /\b(pgoum|nn\.?uu|normas urban|capítulo|modificación del capítulo|condiciones particulares del uso|protección y mejora del uso|instrumento de planeamiento general|cubiertas verdes en la ciudad)\b/i;

const SECTOR_RE =
  /\b(plan parcial|plan especial|estudio de detalle|reparcelación|unidad de ejecución|ámbito|sector)\b/i;

export function clasificarExpediente(exp: UbicacionSigmaExpediente): UbicacionExpedienteCategoria {
  const d = (exp.denominacion || "").toLowerCase();
  if (NORMATIVA_CIUDAD_RE.test(d)) return "normativa_ciudad";
  if (SECTOR_RE.test(d)) return "sector";
  return "local";
}

export function categoriaExpedienteLabel(cat: UbicacionExpedienteCategoria): string {
  switch (cat) {
    case "local":
      return "Actuación en la zona";
    case "sector":
      return "Planeamiento de sector";
    case "normativa_ciudad":
      return "Normas generales (PGOUM)";
  }
}

export function faseEnLenguajeClaro(fase: string | null): string {
  if (!fase) return "En tramitación";
  const f = fase.toLowerCase();
  if (f.includes("aprobación definitiva") || f.includes("aprobacion definitiva")) {
    return "Aprobado";
  }
  if (f.includes("información pública") || f.includes("informacion publica")) {
    return "En información pública";
  }
  if (f.includes("proyecto") || f.includes("redacción")) return "En redacción";
  return fase;
}

import {
  licenciaNotaDesdeTipo,
  licenciaTituloDesdeTipo,
} from "@/lib/licencia-tipos";

export {
  NOTA_DECLARACION_RESPONSABLE,
  NOTA_LICENCIA_URBANISTICA,
  NOTA_LICENCIA_FUNCIONAMIENTO,
  NOTA_OBRA_LICENCIA,
  esDeclaracionResponsable,
  esLicenciaUrbanistica,
  esLicenciaFuncionamiento,
  licenciaNotaDesdeTipo,
  licenciaTituloDesdeTipo,
  clasificarLicenciaFamilia,
} from "@/lib/licencia-tipos";

export function licenciaResumenCorto(lic: UbicacionLicencia): string {
  return licenciaTituloDesdeTipo(lic.tipo_expediente);
}

export function parseFechaEs(raw: string | null): Date | null {
  if (!raw) return null;
  const p = raw.trim().split(/[/.-]/);
  if (p.length < 3) return null;
  const d = Number(p[0]);
  const m = Number(p[1]);
  const y = Number(p[2].length === 2 ? `20${p[2]}` : p[2]);
  if (!d || !m || !y) return null;
  return new Date(y, m - 1, d);
}

function startOfLocalDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function isoDateLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Etiqueta relativa en español (p. ej. «hace 3 días») + fecha ISO para `<time>`. */
export function fechaRelativaEs(
  raw: string | null | undefined,
  ref: Date = new Date(),
): { label: string; iso: string | null; title: string | null } {
  const trimmed = raw?.trim();
  const parsed = parseFechaEs(trimmed ?? null);
  if (!parsed) {
    return { label: trimmed || "Sin fecha", iso: null, title: null };
  }

  const iso = isoDateLocal(parsed);
  const title = trimmed || iso;

  const diffDays = Math.round(
    (startOfLocalDay(ref).getTime() - startOfLocalDay(parsed).getTime()) / 86_400_000,
  );

  if (diffDays === 0) return { label: "Hoy", iso, title };
  if (diffDays === 1) return { label: "Ayer", iso, title };
  if (diffDays === -1) return { label: "Mañana", iso, title };

  if (diffDays > 0) {
    if (diffDays < 7) {
      return { label: diffDays === 1 ? "Hace 1 día" : `Hace ${diffDays} días`, iso, title };
    }
    const weeks = Math.floor(diffDays / 7);
    if (weeks < 5) {
      return {
        label: weeks === 1 ? "Hace 1 semana" : `Hace ${weeks} semanas`,
        iso,
        title,
      };
    }
    const months = Math.floor(diffDays / 30);
    if (months < 12) {
      return { label: months === 1 ? "Hace 1 mes" : `Hace ${months} meses`, iso, title };
    }
    const years = Math.floor(diffDays / 365);
    return { label: years === 1 ? "Hace 1 año" : `Hace ${years} años`, iso, title };
  }

  const ahead = -diffDays;
  if (ahead < 7) {
    return { label: ahead === 1 ? "En 1 día" : `En ${ahead} días`, iso, title };
  }
  const weeks = Math.floor(ahead / 7);
  if (weeks < 5) {
    return { label: weeks === 1 ? "En 1 semana" : `En ${weeks} semanas`, iso, title };
  }
  const months = Math.floor(ahead / 30);
  if (months < 12) {
    return { label: months === 1 ? "En 1 mes" : `En ${months} meses`, iso, title };
  }
  const years = Math.floor(ahead / 365);
  return { label: years === 1 ? "En 1 año" : `En ${years} años`, iso, title };
}

export type UbicacionResumen = {
  parrafo: string;
  bullets: string[];
  hayObraReciente: boolean;
  hayNormativaPgoum: boolean;
  licenciasRecientes: UbicacionLicencia[];
  expedientesPorCategoria: Record<UbicacionExpedienteCategoria, UbicacionSigmaExpediente[]>;
  hitos: Array<{
    fecha: string | null;
    fechaSort: number;
    titulo: string;
    detalle: string;
    tipo: "licencia" | "sigma";
    href?: string;
    nota?: string | null;
  }>;
};

export function buildUbicacionResumen(
  ficha: UbicacionFicha,
  metricsByExpediente: Record<string, SigmaExpedienteMetric | null> = {},
): UbicacionResumen {
  const licencias = [...ficha.licencias].sort((a, b) => {
    const da = parseFechaEs(a.fecha_concesion || a.fecha_alta)?.getTime() ?? 0;
    const db = parseFechaEs(b.fecha_concesion || b.fecha_alta)?.getTime() ?? 0;
    return db - da;
  });

  const expedientesPorCategoria: Record<UbicacionExpedienteCategoria, UbicacionSigmaExpediente[]> = {
    local: [],
    sector: [],
    normativa_ciudad: [],
  };
  for (const exp of ficha.expedientesSigma) {
    expedientesPorCategoria[clasificarExpediente(exp)].push(exp);
  }

  const hayNormativaPgoum = expedientesPorCategoria.normativa_ciudad.length > 0;
  const licenciasRecientes = licencias.slice(0, 5);
  const ultimaLic = licenciasRecientes[0];
  const hayObraReciente = licencias.length > 0;

  const bullets: string[] = [];
  if (hayObraReciente && ultimaLic) {
    const cuando = ultimaLic.fecha_concesion || ultimaLic.fecha_alta;
    const uso = ultimaLic.uso ? ` (${ultimaLic.uso.toLowerCase()})` : "";
    bullets.push(
      `Última actuación en el edificio: ${licenciaResumenCorto(ultimaLic)}${uso}${cuando ? `, ${cuando}` : ""}.`,
    );
  } else {
    bullets.push("No hay licencias recientes registradas en esta dirección en el open data del Ayuntamiento.");
  }

  const nLocal = expedientesPorCategoria.local.length + expedientesPorCategoria.sector.length;
  if (nLocal > 0) {
    bullets.push(
      `${nLocal} expediente${nLocal > 1 ? "s" : ""} de planeamiento del sector afectan a esta ubicación.`,
    );
  }
  if (hayNormativaPgoum) {
    bullets.push(
      `Además, ${expedientesPorCategoria.normativa_ciudad.length} cambio${expedientesPorCategoria.normativa_ciudad.length > 1 ? "s" : ""} de normas del Plan General (PGOUM) pasan por aquí: regulan usos a escala de ciudad, no una obra concreta en tu parcela.`,
    );
  }
  if (ficha.expedientesSigma.length === 0 && !hayObraReciente) {
    bullets.push("No hemos detectado planeamiento SIGMA ni licencias en esta coordenada.");
  }

  const conViviendas = ficha.expedientesSigma.filter(
    (e) => (metricsByExpediente[e.expediente_grupo]?.num_viviendas_max ?? 0) > 0,
  );
  if (conViviendas.length > 0) {
    const max = Math.max(
      ...conViviendas.map((e) => metricsByExpediente[e.expediente_grupo]!.num_viviendas_max!),
    );
    bullets.push(
      `Algún ámbito cercano contempla hasta ${max.toLocaleString("es-ES")} viviendas nuevas (cifra orientativa del expediente, no solo de este edificio).`,
    );
  }

  const parrafo =
    ficha.expedientesSigma.length > 0 && hayObraReciente
      ? `En ${ficha.inmueble.direccion || "esta ubicación"} conviven actividad de obra/licencia en el edificio y varias capas de planeamiento que definen qué se puede hacer en el entorno.`
      : ficha.expedientesSigma.length > 0
        ? `Esta dirección está dentro de ${ficha.expedientesSigma.length} ámbito${ficha.expedientesSigma.length > 1 ? "s" : ""} de planeamiento aprobado${ficha.expedientesSigma.length > 1 ? "s" : ""}; en muchos casos son normas de ciudad, no un proyecto de obra en tu puerta.`
        : hayObraReciente
          ? `Aquí constan ${ficha.stats.licenciasTotal} licencias en el registro municipal; revisa la actividad reciente en el edificio.`
          : `De momento no hay señales claras de obra ni de expedientes de planeamiento en este punto.`;

  const hitos: UbicacionResumen["hitos"] = [];

  for (const lic of licencias.slice(0, 8)) {
    const f = lic.fecha_concesion || lic.fecha_alta;
    hitos.push({
      fecha: f,
      fechaSort: parseFechaEs(f)?.getTime() ?? 0,
      titulo: licenciaResumenCorto(lic),
      detalle: [lic.uso, lic.procedimiento].filter(Boolean).join(" · ") || "Licencia urbanística",
      tipo: "licencia",
      nota: licenciaNotaDesdeTipo(lic.tipo_expediente),
    });
  }

  for (const exp of ficha.expedientesSigma) {
    const tram: UbicacionTramite[] = ficha.tramitacionSigma[exp.expediente_grupo] || [];
    const ultimo = tram[tram.length - 1];
    const cat = clasificarExpediente(exp);
    hitos.push({
      fecha: ultimo?.fecha ?? null,
      fechaSort: parseFechaEs(ultimo?.fecha ?? null)?.getTime() ?? 0,
      titulo: (exp.denominacion || exp.expediente_grupo).slice(0, 72),
      detalle: `${categoriaExpedienteLabel(cat)} · ${faseEnLenguajeClaro(exp.fase)}`,
      tipo: "sigma",
      href: `/sigma/${encodeURIComponent(exp.expediente_grupo.replace(/\//g, "-"))}`,
    });
  }

  hitos.sort((a, b) => b.fechaSort - a.fechaSort);

  return {
    parrafo,
    bullets,
    hayObraReciente,
    hayNormativaPgoum,
    licenciasRecientes,
    expedientesPorCategoria,
    hitos: hitos.slice(0, 12),
  };
}
