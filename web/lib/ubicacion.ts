import type { ActuacionEdificioInput } from "@/lib/actuacion-edificio";

export type UbicacionMapProperties = {
  ndp: string;
  direccion: string | null;
  distrito: string | null;
  barrio: string | null;
  licencias: number;
  sigma: number;
  /** Tipo de la licencia más reciente en el edificio (open data Ayto.). */
  ultimaLicenciaTipo?: string | null;
  ultimaLicenciaObjeto?: string | null;
  ultimaLicenciaUso?: string | null;
  ultimaLicenciaProcedimiento?: string | null;
  /** Código normalizado «qué se va a hacer» (ver actuacion-edificio). */
  actuacionQue?: string | null;
  actuacionQueLabel?: string | null;
  /** Fecha de la licencia más reciente (YYYY-MM-DD). */
  ultimaLicenciaFecha?: string | null;
};

export type UbicacionSearchItem = {
  ndp: string;
  direccion: string;
  distrito: string;
  barrio: string;
  label: string;
};

export type UbicacionInmueble = {
  id: number;
  ndp_edificio: string;
  direccion: string | null;
  distrito: string | null;
  barrio: string | null;
  lat: number | null;
  lng: number | null;
  coord_source: string | null;
};

export type UbicacionLicencia = {
  id: number;
  licencia_key: string;
  anio_dataset: number | null;
  fecha_alta: string | null;
  fecha_concesion: string | null;
  procedimiento: string | null;
  tipo_expediente: string | null;
  uso: string | null;
  interesado: string | null;
  objeto: string | null;
  unidad: string | null;
};

export type UbicacionSigmaExpediente = {
  expediente_grupo: string;
  exp_numero_original: string;
  sigma_layer_kind: string | null;
  denominacion: string | null;
  fase: string | null;
  enlace: string | null;
  match_method: string | null;
  match_score: number | null;
};

export type UbicacionTramite = {
  fecha: string | null;
  tramite: string | null;
  organo: string | null;
};

export type UbicacionFicha = {
  inmueble: UbicacionInmueble;
  licencias: UbicacionLicencia[];
  expedientesSigma: UbicacionSigmaExpediente[];
  tramitacionSigma: Record<string, UbicacionTramite[]>;
  stats: {
    licenciasTotal: number;
    expedientesSigma: number;
  };
};

export function actuacionDesdeMapProps(p: UbicacionMapProperties): ActuacionEdificioInput {
  return {
    tipo_expediente: p.ultimaLicenciaTipo,
    objeto: p.ultimaLicenciaObjeto,
    uso: p.ultimaLicenciaUso,
    procedimiento: p.ultimaLicenciaProcedimiento,
  };
}

export function ubicacionPath(ndp: string) {
  return `/ubicacion/${encodeURIComponent(ndp)}`;
}

export function sigmaSlugFromExpediente(exp: string) {
  return encodeURIComponent(exp.replace(/\//g, "-"));
}
