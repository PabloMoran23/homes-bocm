/** Misma lógica que lib/licencia-tipos.ts → clasificarLicenciaMapa (para scripts Node). */

export const LICENCIA_MAPA_LABELS = {
  dr_residencial: "Obras menores en vivienda",
  dr_actividad: "Apertura o cambio en local",
  dr_otra: "Trámite rápido de obra o actividad",
  lu_residencial: "Obras con licencia en vivienda",
  lu_actividad: "Obras o actividad en local",
  lu_otra: "Obra o actuación autorizada",
  funcionamiento_residencial: "Vivienda autorizada para uso",
  funcionamiento_actividad: "Local autorizado para abrir",
  comunicacion_previa: "Obra comunicada al Ayuntamiento",
  primera_ocupacion: "Edificio listo para ocupar",
  obra_local_vivienda: "Local convertido en vivienda",
  obra_edificio: "Obra en el edificio",
  consulta: "Consulta o parcelación",
  otra: "Otros trámites",
};

export const LICENCIA_MAPA_COLORS = {
  dr_residencial: "#d97706",
  dr_actividad: "#7c3aed",
  dr_otra: "#ca8a04",
  lu_residencial: "#0f766e",
  lu_actividad: "#2563eb",
  lu_otra: "#0891b2",
  funcionamiento_residencial: "#059669",
  funcionamiento_actividad: "#4f46e5",
  comunicacion_previa: "#ea580c",
  primera_ocupacion: "#16a34a",
  obra_local_vivienda: "#c026d3",
  obra_edificio: "#78716c",
  consulta: "#0d9488",
  otra: "#475569",
};

/** Orden de leyenda del mapa (mismas series prioritarias). */
export const LICENCIA_MAPA_LEYENDA = [
  "dr_residencial",
  "dr_actividad",
  "lu_residencial",
  "lu_actividad",
  "funcionamiento_residencial",
  "funcionamiento_actividad",
  "comunicacion_previa",
  "primera_ocupacion",
  "obra_local_vivienda",
  "obra_edificio",
  "otra",
];

function normTipoExpediente(raw) {
  return String(raw || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function esDeclaracionResponsable(tipoExpediente) {
  const t = normTipoExpediente(tipoExpediente);
  return t.includes("declaracion responsable") || t.includes("lic. declaracion responsable");
}

function esLicenciaUrbanistica(tipoExpediente) {
  if (esDeclaracionResponsable(tipoExpediente)) return false;
  const t = normTipoExpediente(tipoExpediente);
  if (t.includes("funcionamiento")) return false;
  if (t.includes("comunicacion previa")) return false;
  return (
    t.includes("licencia urban") ||
    t.includes("lic. urban") ||
    t.includes("licencia basica urbanistica") ||
    (t.includes("licencias") && t.includes("procedimiento ordinario") && t.includes("urbanistica"))
  );
}

export function clasificarLicenciaMapa(tipoExpediente) {
  const t = normTipoExpediente(tipoExpediente);
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

export function labelMapaCategoria(cat) {
  return LICENCIA_MAPA_LABELS[cat] || cat;
}
