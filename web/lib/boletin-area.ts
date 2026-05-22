import type { UbicacionExpedienteCategoria } from "@/lib/ubicacion-resumen";

export type BoletinEvento = {
  tipo: "licencia" | "sigma";
  fecha: string | null;
  distanciaM?: number;
  /** `tipo_expediente` del Ayuntamiento (licencias); denominación (SIGMA). */
  titulo: string;
  detalle: string;
  ndp?: string | null;
  direccion?: string | null;
  distrito?: string | null;
  expedienteGrupo?: string;
  contienePunto?: boolean;
  sigmaLayerKind?: string | null;
  lat?: number;
  lng?: number;
};

export type BoletinAreaResult = {
  center: {
    lat: number;
    lng: number;
    ndp?: string | null;
    direccion?: string | null;
    distrito?: string | null;
    barrio?: string | null;
  };
  params: {
    radiusM: number;
    months: number;
  };
  stats: {
    licencias: number;
    expedientesSigma: number;
    eventos: number;
  };
  licencias: BoletinEvento[];
  expedientesSigma: BoletinEvento[];
  timeline: BoletinEvento[];
  error?: string;
};

export const RADIUS_OPTIONS = [
  { m: 300, label: "300 m" },
  { m: 500, label: "500 m" },
  { m: 800, label: "800 m" },
  { m: 1200, label: "1,2 km" },
] as const;

export const MONTHS_OPTIONS = [
  { months: 12, label: "Último año" },
  { months: 24, label: "2 años" },
  { months: 36, label: "3 años" },
] as const;

export function boletinPath(ndp: string) {
  return `/boletin?ndp=${encodeURIComponent(ndp)}`;
}

export function boletinResumenParrafo(data: BoletinAreaResult): string {
  const { stats, params } = data;
  const r = params.radiusM;
  if (stats.eventos === 0) {
    return `No hemos encontrado licencias ni hitos de planeamiento recientes en un radio de ${r} m. Prueba ampliar el radio o el periodo.`;
  }
  const parts: string[] = [];
  if (stats.licencias > 0) {
    parts.push(
      `${stats.licencias} licencia${stats.licencias > 1 ? "s" : ""} en edificios cercanos`,
    );
  }
  if (stats.expedientesSigma > 0) {
    parts.push(
      `${stats.expedientesSigma} proyecto${stats.expedientesSigma > 1 ? "s" : ""} de planeamiento que afectan la zona`,
    );
  }
  return `En los últimos ${params.months} meses, en ${r} m a la redonda: ${parts.join(" y ")}.`;
}

export { clasificarExpediente, categoriaExpedienteLabel } from "@/lib/ubicacion-resumen";
export type { UbicacionExpedienteCategoria };
