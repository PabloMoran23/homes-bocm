/**
 * Títulos en lenguaje claro para `tipo_expediente` del Ayuntamiento de Madrid.
 * Las reglas se evalúan en orden: la primera que coincida gana.
 */

export const NOTA_DECLARACION_RESPONSABLE =
  "Hemos detectado una declaración responsable en esta ubicación.";

export const NOTA_LICENCIA_URBANISTICA =
  "Permiso municipal concedido en esta ubicación; no indica si la obra ha empezado o terminado.";

export const NOTA_LICENCIA_FUNCIONAMIENTO =
  "Autorización de uso o apertura registrada; no indica si el local o la vivienda ya está en uso.";

export const NOTA_OBRA_LICENCIA =
  "Permiso de obra registrado; no indica si los trabajos han empezado o terminado.";

export type LicenciaFamilia =
  | "declaracion_responsable"
  | "licencia_urbanistica"
  | "funcionamiento"
  | "comunicacion_previa"
  | "primera_ocupacion"
  | "obra"
  | "consulta"
  | "otro";

type ReglaTipo = {
  when: (t: string) => boolean;
  titulo: string;
  familia: LicenciaFamilia;
  nota?: string;
};

export function normTipoExpediente(raw: string): string {
  return raw
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function esDeclaracionResponsable(tipoExpediente: string | null | undefined): boolean {
  const t = normTipoExpediente(tipoExpediente || "");
  return t.includes("declaracion responsable") || t.includes("lic. declaracion responsable");
}

export function esLicenciaUrbanistica(tipoExpediente: string | null | undefined): boolean {
  if (esDeclaracionResponsable(tipoExpediente)) return false;
  const t = normTipoExpediente(tipoExpediente || "");
  if (t.includes("funcionamiento")) return false;
  if (t.includes("comunicacion previa")) return false;
  return (
    t.includes("licencia urban") ||
    t.includes("lic. urban") ||
    t.includes("licencia basica urbanistica") ||
    (t.includes("licencias") && t.includes("procedimiento ordinario") && t.includes("urbanistica"))
  );
}

export function esLicenciaFuncionamiento(tipoExpediente: string | null | undefined): boolean {
  if (esDeclaracionResponsable(tipoExpediente)) return false;
  const t = normTipoExpediente(tipoExpediente || "");
  return t.includes("funcionamiento") || t.includes("implantacion de actividad") || t.includes("implantacion o modificacion de actividad");
}

const REGLAS: ReglaTipo[] = [
  // —— Declaración responsable (específicas) ——
  {
    when: (t) => t.includes("declaracion responsable residencial"),
    titulo: "Reforma o obra menor en vivienda (Declaración Responsable Residencial)",
    familia: "declaracion_responsable",
    nota: NOTA_DECLARACION_RESPONSABLE,
  },
  {
    when: (t) => t.includes("declaracion responsable actividad"),
    titulo: "Apertura o cambio de actividad en un local (Declaración Responsable Actividad)",
    familia: "declaracion_responsable",
    nota: NOTA_DECLARACION_RESPONSABLE,
  },
  {
    when: (t) =>
      t.includes("declaracion responsable") &&
      (t.includes("primera ocupacion") || t.includes("ocupacion")),
    titulo: "Primera ocupación del inmueble (declaración responsable)",
    familia: "declaracion_responsable",
    nota: NOTA_DECLARACION_RESPONSABLE,
  },
  {
    when: (t) => t.includes("declaracion responsable") && t.includes("funcionamiento"),
    titulo: "Uso o apertura autorizada (declaración responsable de funcionamiento)",
    familia: "declaracion_responsable",
    nota: NOTA_DECLARACION_RESPONSABLE,
  },
  {
    when: (t) => t.includes("declaracion responsable") && t.includes("obra"),
    titulo: "Obra autorizada por declaración responsable",
    familia: "declaracion_responsable",
    nota: NOTA_DECLARACION_RESPONSABLE,
  },
  {
    when: (t) => t.includes("declaracion responsable") && t.includes("sin certificado"),
    titulo: "Trámite por declaración responsable (sin certificado de conformidad)",
    familia: "declaracion_responsable",
    nota: NOTA_DECLARACION_RESPONSABLE,
  },
  {
    when: (t) => t.includes("declaracion responsable"),
    titulo: "Declaración responsable registrada",
    familia: "declaracion_responsable",
    nota: NOTA_DECLARACION_RESPONSABLE,
  },

  // —— Licencia urbanística ——
  {
    when: (t) => t.includes("licencia urbanistica") && t.includes("actividad"),
    titulo: "Obra o actividad en local (licencia urbanística de actividad)",
    familia: "licencia_urbanistica",
    nota: NOTA_LICENCIA_URBANISTICA,
  },
  {
    when: (t) => t.includes("licencia urbanistica") && t.includes("residencial"),
    titulo: "Reforma u obra en vivienda (licencia urbanística)",
    familia: "licencia_urbanistica",
    nota: NOTA_LICENCIA_URBANISTICA,
  },
  {
    when: (t) =>
      (t.includes("licencia urbanistica") || t.includes("lic. urbanistica")) &&
      !t.includes("funcionamiento"),
    titulo: "Obra o actuación autorizada (licencia urbanística)",
    familia: "licencia_urbanistica",
    nota: NOTA_LICENCIA_URBANISTICA,
  },
  {
    when: (t) => t.includes("licencia basica urbanistica") && t.includes("actividad"),
    titulo: "Actividad en local (licencia básica urbanística de actividad)",
    familia: "licencia_urbanistica",
    nota: NOTA_LICENCIA_URBANISTICA,
  },
  {
    when: (t) => t.includes("licencia basica urbanistica"),
    titulo: "Obra en vivienda (licencia básica urbanística)",
    familia: "licencia_urbanistica",
    nota: NOTA_LICENCIA_URBANISTICA,
  },

  // —— Funcionamiento (no DR) ——
  {
    when: (t) => t.includes("funcionamiento") && t.includes("residencial"),
    titulo: "Uso autorizado de la vivienda (licencia de funcionamiento residencial)",
    familia: "funcionamiento",
    nota: NOTA_LICENCIA_FUNCIONAMIENTO,
  },
  {
    when: (t) =>
      t.includes("funcionamiento") &&
      (t.includes("actividad") || t.includes("ecu")),
    titulo: "Apertura o actividad en local (licencia de funcionamiento)",
    familia: "funcionamiento",
    nota: NOTA_LICENCIA_FUNCIONAMIENTO,
  },
  {
    when: (t) => t.includes("funcionamiento"),
    titulo: "Autorización de uso del inmueble (licencia de funcionamiento)",
    familia: "funcionamiento",
    nota: NOTA_LICENCIA_FUNCIONAMIENTO,
  },
  {
    when: (t) =>
      t.includes("implantacion") &&
      (t.includes("actividad") || t.includes("modificacion de actividad")),
    titulo: "Nueva actividad o cambio de negocio en local",
    familia: "funcionamiento",
    nota: NOTA_LICENCIA_FUNCIONAMIENTO,
  },

  // —— Comunicación previa ——
  {
    when: (t) => t.includes("comunicacion previa"),
    titulo: "Obra comunicada al Ayuntamiento (comunicación previa)",
    familia: "comunicacion_previa",
    nota: NOTA_OBRA_LICENCIA,
  },

  // —— Primera ocupación ——
  {
    when: (t) => t.includes("primera ocupacion"),
    titulo: "Primera ocupación del edificio o local",
    familia: "primera_ocupacion",
  },

  // —— Obras concretas ——
  {
    when: (t) =>
      t.includes("transformacion") &&
      (t.includes("local") || t.includes("locales")) &&
      t.includes("vivienda"),
    titulo: "Cambio de local a vivienda",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.includes("nueva planta") || t.includes("ampliacion") || t.includes("sustitucion"),
    titulo: "Obra de nueva planta o ampliación del edificio",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.includes("reestructuracion") || t.includes("reconfiguracion"),
    titulo: "Reforma o reestructuración del edificio",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) =>
      t.includes("conservacion") ||
      t.includes("consolidacion") ||
      t.includes("restauracion") ||
      t.includes("refuerzo"),
    titulo: "Obras de conservación o refuerzo del edificio",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.includes("demolicion"),
    titulo: "Demolición autorizada",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) =>
      t.includes("obras exteriores") ||
      t.includes("obras en exteriores") ||
      t.includes("cerramiento") ||
      t.includes("vallado") ||
      t.includes("piscina"),
    titulo: "Obra en patio, fachada o exterior del edificio",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.includes("acondicionamiento"),
    titulo: "Acondicionamiento interior o de instalaciones",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.includes("incrementar") && t.includes("vivienda"),
    titulo: "Obra para aumentar el número de viviendas",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.includes("instalacion") && (t.includes("maquinaria") || t.includes("andamio")),
    titulo: "Instalación de andamios o maquinaria en obra",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.startsWith("obras ") || t.startsWith("obra ") || t.includes(" obras "),
    titulo: "Obra en el edificio",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },

  // —— Consultas y parcelación ——
  {
    when: (t) => t.includes("consulta urbanistica"),
    titulo: "Consulta urbanística (sin obra directa)",
    familia: "consulta",
  },
  {
    when: (t) => t.includes("parcelacion"),
    titulo: "Parcelación o división del suelo",
    familia: "consulta",
  },
  {
    when: (t) => t.includes("modificacion") && t.includes("licencia"),
    titulo: "Modificación de una licencia anterior",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
  {
    when: (t) => t.includes("talas") || t.includes("tala"),
    titulo: "Tala o poda de árboles",
    familia: "obra",
  },
  {
    when: (t) => t.includes("evaluacion ambiental"),
    titulo: "Actividad con trámite ambiental",
    familia: "funcionamiento",
  },
  {
    when: (t) => t.includes("publicidad exterior"),
    titulo: "Publicidad exterior en fachada",
    familia: "obra",
  },
  {
    when: (t) => t.includes("procedimiento ordinario") || t.includes("procedimiento abreviado"),
    titulo: "Tramitación urbanística ordinaria",
    familia: "obra",
    nota: NOTA_OBRA_LICENCIA,
  },
];

function tituloFallback(raw: string): string {
  const limpio = raw.replace(/\s+/g, " ").trim();
  if (!limpio) return "Tramitación urbanística";
  if (limpio.length <= 72) return limpio;
  return `${limpio.slice(0, 69)}…`;
}

export function clasificarLicenciaFamilia(
  tipoExpediente: string | null | undefined,
): LicenciaFamilia {
  const t = normTipoExpediente(tipoExpediente || "");
  for (const regla of REGLAS) {
    if (regla.when(t)) return regla.familia;
  }
  return "otro";
}

export function licenciaTituloDesdeTipo(tipoExpediente: string | null | undefined): string {
  const raw = (tipoExpediente || "").trim();
  const t = normTipoExpediente(raw);
  if (!t) return "Tramitación urbanística";
  for (const regla of REGLAS) {
    if (regla.when(t)) return regla.titulo;
  }
  return tituloFallback(raw);
}

export function licenciaNotaDesdeTipo(tipoExpediente: string | null | undefined): string | null {
  const t = normTipoExpediente(tipoExpediente || "");
  if (!t) return null;
  for (const regla of REGLAS) {
    if (regla.when(t)) return regla.nota ?? null;
  }
  return null;
}

/** Subtipo para iconos del mapa (más fino que familia). */
export type LicenciaMapaCategoria =
  | "dr_residencial"
  | "dr_actividad"
  | "dr_otra"
  | "lu_residencial"
  | "lu_actividad"
  | "lu_otra"
  | "funcionamiento_residencial"
  | "funcionamiento_actividad"
  | "comunicacion_previa"
  | "primera_ocupacion"
  | "obra_local_vivienda"
  | "obra_edificio"
  | "consulta"
  | "otra";

export function clasificarLicenciaMapa(
  tipoExpediente: string | null | undefined,
): LicenciaMapaCategoria {
  const t = normTipoExpediente(tipoExpediente || "");
  if (t.includes("declaracion responsable residencial")) return "dr_residencial";
  if (t.includes("declaracion responsable actividad")) return "dr_actividad";
  if (esDeclaracionResponsable(tipoExpediente)) return "dr_otra";
  if (t.includes("licencia urbanistica") && t.includes("actividad")) return "lu_actividad";
  if (t.includes("licencia urbanistica") && t.includes("residencial")) return "lu_residencial";
  if (esLicenciaUrbanistica(tipoExpediente)) return "lu_otra";
  if (t.includes("funcionamiento") && t.includes("residencial")) return "funcionamiento_residencial";
  if (t.includes("funcionamiento") || t.includes("implantacion")) return "funcionamiento_actividad";
  if (t.includes("comunicacion previa")) return "comunicacion_previa";
  if (t.includes("primera ocupacion")) return "primera_ocupacion";
  if (
    t.includes("transformacion") &&
    (t.includes("local") || t.includes("locales")) &&
    t.includes("vivienda")
  ) {
    return "obra_local_vivienda";
  }
  if (t.includes("consulta") || t.includes("parcelacion")) return "consulta";
  if (
    t.includes("obra") ||
    t.includes("reestructuracion") ||
    t.includes("demolicion") ||
    t.includes("acondicionamiento") ||
    t.includes("conservacion") ||
    t.includes("nueva planta")
  ) {
    return "obra_edificio";
  }
  return "otra";
}
