import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import { tramiteShortLabel } from "@/lib/sigma-user-labels";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import { tramiteKind } from "@/lib/tramite-style";
import type {
  UbicacionFicha,
  UbicacionLicencia,
  UbicacionSigmaExpediente,
  UbicacionTramite,
} from "@/lib/ubicacion";

export type ExpedienteFechaDestacada = {
  fecha: string | null;
  fechaSort: number;
  hitoLabel: string | null;
  /** Fecha inferida solo del año en la referencia municipal (p. ej. 135/2023/02073). */
  soloAnio?: boolean;
};

const MILESTONE_KINDS = ["definitiva", "provisional", "inicial"] as const;

export type ExpedienteFechaInput = {
  expediente_grupo: string;
  exp_numero_original?: string | null;
  fecha_aprob?: string | null;
};

/** Año en referencias Ayto. tipo «135/2023/02073» (segundo tramo). */
export function anioReferenciaMunicipal(exp: ExpedienteFechaInput): number | null {
  for (const ref of [exp.exp_numero_original, exp.expediente_grupo]) {
    if (!ref) continue;
    const parts = ref.trim().split("/");
    if (parts.length < 2) continue;
    const y = Number(parts[1]);
    if (Number.isInteger(y) && y >= 1980 && y <= 2100) return y;
  }
  return null;
}

/** Fecha clave del expediente para ordenar la cronología de la zona (aprobación > último hito). */
export function fechaDestacadaExpediente(tramites: UbicacionTramite[]): ExpedienteFechaDestacada {
  if (!tramites.length) {
    return { fecha: null, fechaSort: 0, hitoLabel: null };
  }

  for (const kind of MILESTONE_KINDS) {
    const hito = tramites.find((t) => t.fecha && tramiteKind(t.tramite) === kind);
    if (hito?.fecha) {
      return fechaDesdeTexto(hito.fecha, tramiteShortLabel(hito.tramite));
    }
  }

  for (let i = tramites.length - 1; i >= 0; i--) {
    const hito = tramites[i];
    if (!hito.fecha) continue;
    return fechaDesdeTexto(hito.fecha, tramiteShortLabel(hito.tramite));
  }

  return { fecha: null, fechaSort: 0, hitoLabel: null };
}

function fechaDesdeTexto(raw: string, hitoLabel: string | null): ExpedienteFechaDestacada {
  const parsed = parseFechaEs(raw);
  if (!parsed) {
    return { fecha: raw.trim() || null, fechaSort: 0, hitoLabel };
  }
  const soloAnio = /^\d{4}$/.test(raw.trim());
  return {
    fecha: raw.trim(),
    fechaSort: parsed.getTime(),
    hitoLabel,
    soloAnio: soloAnio || undefined,
  };
}

/** Tramitación del visor + año de referencia municipal + fecha_aprob del catálogo. */
export function fechaDestacadaUbicacionExpediente(
  exp: ExpedienteFechaInput,
  tramites: UbicacionTramite[],
): ExpedienteFechaDestacada {
  const fromTramites = fechaDestacadaExpediente(tramites);
  if (fromTramites.fecha && fromTramites.fechaSort > 0) return fromTramites;

  if (exp.fecha_aprob) {
    const parsed = parseFechaEs(exp.fecha_aprob);
    if (parsed) {
      return {
        fecha: formatFechaEs(parsed),
        fechaSort: parsed.getTime(),
        hitoLabel: "Fecha de aprobación",
      };
    }
  }

  const anio = anioReferenciaMunicipal(exp);
  if (anio) {
    return {
      fecha: String(anio),
      fechaSort: new Date(anio, 0, 1).getTime(),
      hitoLabel: "Año del expediente",
      soloAnio: true,
    };
  }

  return fromTramites;
}

function formatFechaEs(d: Date): string {
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  return `${day}/${month}/${d.getFullYear()}`;
}

export function ordenarExpedientesPorFecha(
  expedientes: UbicacionSigmaExpediente[],
  tramitacionSigma: Record<string, UbicacionTramite[]>,
): UbicacionSigmaExpediente[] {
  return [...expedientes].sort((a, b) => {
    const fa = fechaDestacadaUbicacionExpediente(
      a,
      tramitacionSigma[a.expediente_grupo] || [],
    ).fechaSort;
    const fb = fechaDestacadaUbicacionExpediente(
      b,
      tramitacionSigma[b.expediente_grupo] || [],
    ).fechaSort;
    if (fa !== fb) {
      if (!fa) return 1;
      if (!fb) return -1;
      return fa - fb;
    }
    return (a.denominacion || a.expediente_grupo).localeCompare(b.denominacion || b.expediente_grupo, "es");
  });
}

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
      return "Cambios en el entorno";
    case "normativa_ciudad":
      return "Normas generales de ciudad";
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
  if (f.includes("inicial")) return "Aprobado inicialmente";
  if (f.includes("provisional")) return "Pendiente de aprobación final";
  if (f.includes("archivo") || f.includes("archiv") || f.includes("desist")) return "Archivado";
  return "En tramitación";
}

import { normalizarActuacionEdificio } from "@/lib/actuacion-edificio";
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
  return normalizarActuacionEdificio(lic).etiqueta;
}

function procedimientoEnLenguajeClaro(raw: string | null | undefined): string | null {
  const s = String(raw || "").trim();
  if (!s) return null;
  const n = s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  if (n.includes("declaracion responsable")) return "Trámite rápido municipal";
  if (n.includes("licencia") && n.includes("funcionamiento")) {
    return "Autorización de uso o apertura";
  }
  if (n.includes("licencia urban")) return "Obra o actuación autorizada";
  if (n.includes("comunicacion previa")) return "Obra comunicada al Ayuntamiento";
  return s;
}

export function licenciaDetalleCorto(lic: UbicacionLicencia): string {
  const norm = normalizarActuacionEdificio(lic);
  if (norm.detalle) return norm.detalle;
  const proc = procedimientoEnLenguajeClaro(lic.procedimiento);
  return [lic.uso, proc].filter(Boolean).join(" · ") || "Obra o actuación autorizada";
}

export function parseFechaEs(raw: string | null): Date | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;

  const iso = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) {
    const y = Number(iso[1]);
    const m = Number(iso[2]);
    const d = Number(iso[3]);
    if (y && m && d) return new Date(y, m - 1, d);
  }

  if (/^\d{4}$/.test(trimmed)) {
    return new Date(Number(trimmed), 0, 1);
  }

  const p = trimmed.split(/[/.-]/);
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
    bullets.push("No hemos encontrado actividad reciente de obra o apertura en esta dirección.");
  }

  const nLocal = expedientesPorCategoria.local.length + expedientesPorCategoria.sector.length;
  if (nLocal > 0) {
    bullets.push(
      `${nLocal} proyecto${nLocal > 1 ? "s" : ""} urbanístico${nLocal > 1 ? "s" : ""} afectan al entorno de esta dirección.`,
    );
  }
  if (hayNormativaPgoum) {
    bullets.push(
      `También hay ${expedientesPorCategoria.normativa_ciudad.length} cambio${expedientesPorCategoria.normativa_ciudad.length > 1 ? "s" : ""} de normas generales: suelen regular usos de ciudad, no una obra concreta en tu edificio.`,
    );
  }
  if (ficha.expedientesSigma.length === 0 && !hayObraReciente) {
    bullets.push("No hemos detectado proyectos urbanísticos ni actividad municipal relevante en este punto.");
  }

  const conViviendas = ficha.expedientesSigma.filter(
    (e) => (metricsByExpediente[e.expediente_grupo]?.num_viviendas_max ?? 0) > 0,
  );
  if (conViviendas.length > 0) {
    const max = Math.max(
      ...conViviendas.map((e) => metricsByExpediente[e.expediente_grupo]!.num_viviendas_max!),
    );
    bullets.push(
      `Algún proyecto cercano menciona hasta ${max.toLocaleString("es-ES")} viviendas nuevas. Es una cifra del ámbito, no necesariamente de este edificio.`,
    );
  }

  const parrafo =
    ficha.expedientesSigma.length > 0 && hayObraReciente
      ? `En ${ficha.inmueble.direccion || "esta ubicación"} hay señales de actividad en el edificio y proyectos urbanísticos que pueden influir en el entorno.`
      : ficha.expedientesSigma.length > 0
        ? `Esta dirección cae dentro de ${ficha.expedientesSigma.length} ámbito${ficha.expedientesSigma.length > 1 ? "s" : ""} urbanístico${ficha.expedientesSigma.length > 1 ? "s" : ""}. Algunos pueden ser cambios generales de normativa, no obras en tu puerta.`
        : hayObraReciente
          ? `Aquí constan ${ficha.stats.licenciasTotal} actuaciones municipales en el edificio; revisa la actividad reciente para entender qué tipo de cambios se han registrado.`
          : `De momento no vemos señales claras de obra, apertura o proyectos urbanísticos en este punto.`;

  const hitos: UbicacionResumen["hitos"] = [];

  for (const lic of licencias.slice(0, 8)) {
    const f = lic.fecha_concesion || lic.fecha_alta;
    hitos.push({
      fecha: f,
      fechaSort: parseFechaEs(f)?.getTime() ?? 0,
      titulo: licenciaResumenCorto(lic),
      detalle: licenciaDetalleCorto(lic),
      tipo: "licencia",
      nota: licenciaNotaDesdeTipo(lic.tipo_expediente),
    });
  }

  for (const exp of ficha.expedientesSigma) {
    const tram: UbicacionTramite[] = ficha.tramitacionSigma[exp.expediente_grupo] || [];
    const { fecha, fechaSort, hitoLabel } = fechaDestacadaUbicacionExpediente(exp, tram);
    const cat = clasificarExpediente(exp);
    hitos.push({
      fecha,
      fechaSort,
      titulo: (exp.denominacion || exp.expediente_grupo).slice(0, 72),
      detalle: [categoriaExpedienteLabel(cat), faseEnLenguajeClaro(exp.fase), hitoLabel]
        .filter(Boolean)
        .join(" · "),
      tipo: "sigma",
      href: sigmaFichaPath(exp.expediente_grupo),
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
