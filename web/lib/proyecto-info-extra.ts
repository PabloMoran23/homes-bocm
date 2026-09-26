export const PROYECTO_INFO_BLOQUES = [
  "situacion",
  "programa",
  "cifras",
  "actores",
  "prensa",
  "cronologia",
] as const;

export type ProyectoInfoBloque = (typeof PROYECTO_INFO_BLOQUES)[number];

export const PROYECTO_INFO_BLOQUE_LABEL: Record<ProyectoInfoBloque, string> = {
  situacion: "Qué está pasando",
  programa: "Qué se va a construir",
  cifras: "Cifras",
  actores: "Quién",
  prensa: "Prensa",
  cronologia: "Cronología",
};

export type ProyectoInfoDato = {
  bloque: ProyectoInfoBloque;
  clave: string | null;
  etiqueta: string;
  valor: string;
  valorNumero: number | null;
  unidad: string | null;
  confianza: "alta" | "media" | "baja";
  fuenteTipo: "oficial" | "prensa" | "web";
  fuenteNombre: string | null;
  fuenteUrl: string | null;
  fuenteFecha: string | null;
  extracto: string | null;
  destacado: boolean;
  orden: number;
};

export type ProyectoInfoHallazgo = {
  titulo: string;
  cuerpo: string;
  fuenteNombre: string | null;
  fuenteUrl: string | null;
  fuenteFecha: string | null;
  orden: number;
};

export type ProyectoInfoExtra = {
  id: number;
  proyectoId: string;
  investigadoAt: string;
  estado: "completa" | "parcial";
  resumen: string;
  huecos: string | null;
  datos: ProyectoInfoDato[];
  hallazgos: ProyectoInfoHallazgo[];
};

const BLOQUES = new Set<string>(PROYECTO_INFO_BLOQUES);

function asText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

export function parseProyectoInfoExtra(raw: unknown): ProyectoInfoExtra | null {
  let value = raw;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value) as unknown;
    } catch {
      return null;
    }
  }
  const row = asRecord(value);
  if (!row) return null;
  const resumen = asText(row.resumen);
  const proyectoId = asText(row.proyectoId);
  const estado = row.estado === "parcial" ? "parcial" : row.estado === "completa" ? "completa" : null;
  if (!resumen || !proyectoId || !estado) return null;

  const datos: ProyectoInfoDato[] = [];
  if (Array.isArray(row.datos)) {
    for (const item of row.datos) {
      const dato = asRecord(item);
      if (!dato) continue;
      const bloque = asText(dato.bloque);
      const etiqueta = asText(dato.etiqueta);
      const valor = asText(dato.valor);
      const confianza = dato.confianza;
      const fuenteTipo = dato.fuenteTipo;
      if (!bloque || !BLOQUES.has(bloque) || !etiqueta || !valor) continue;
      if (confianza !== "alta" && confianza !== "media" && confianza !== "baja") continue;
      if (fuenteTipo !== "oficial" && fuenteTipo !== "prensa" && fuenteTipo !== "web") continue;
      datos.push({
        bloque: bloque as ProyectoInfoBloque,
        clave: asText(dato.clave),
        etiqueta,
        valor,
        valorNumero: typeof dato.valorNumero === "number" ? dato.valorNumero : null,
        unidad: asText(dato.unidad),
        confianza,
        fuenteTipo,
        fuenteNombre: asText(dato.fuenteNombre),
        fuenteUrl: asText(dato.fuenteUrl),
        fuenteFecha: asText(dato.fuenteFecha),
        extracto: asText(dato.extracto),
        destacado: dato.destacado === true,
        orden: typeof dato.orden === "number" ? dato.orden : datos.length,
      });
    }
  }

  const hallazgos: ProyectoInfoHallazgo[] = [];
  if (Array.isArray(row.hallazgos)) {
    for (const item of row.hallazgos) {
      const hallazgo = asRecord(item);
      if (!hallazgo) continue;
      const titulo = asText(hallazgo.titulo);
      const cuerpo = asText(hallazgo.cuerpo);
      if (!titulo || !cuerpo) continue;
      hallazgos.push({
        titulo,
        cuerpo,
        fuenteNombre: asText(hallazgo.fuenteNombre),
        fuenteUrl: asText(hallazgo.fuenteUrl),
        fuenteFecha: asText(hallazgo.fuenteFecha),
        orden: typeof hallazgo.orden === "number" ? hallazgo.orden : hallazgos.length,
      });
    }
  }

  return {
    id: typeof row.id === "number" ? row.id : 0,
    proyectoId,
    investigadoAt: asText(row.investigadoAt) || "",
    estado,
    resumen,
    huecos: asText(row.huecos),
    datos,
    hallazgos,
  };
}
