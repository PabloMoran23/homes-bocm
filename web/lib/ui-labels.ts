/**
 * Textos de producto: lenguaje claro para el usuario (sin SIGMA / expediente técnico).
 */
export const ACTIVIDAD_EN_MAPA = "Actividad en el mapa";
export const OBRA = "Obra";
export const PLAN_EN_TRAMITACION = "Plan en tramitación";
export const DASHBOARD = "Dashboard";

/** @deprecated Prefer ACTIVIDAD_EN_MAPA or planEnTramitacionEnVista */
export const PROYECTOS_URBANISTICOS = "Actividad urbanística";
export const PROYECTOS = "Planes";
export const PROYECTO = "Plan";

export const actuacionesEnVista = (n: number) =>
  `${n.toLocaleString("es-ES")} actuacion${n === 1 ? "" : "es"} en el mapa`;

export const planEnTramitacionEnVista = (n: number) =>
  `${n.toLocaleString("es-ES")} plan${n === 1 ? "" : "es"} en el mapa`;

/** @deprecated Use planEnTramitacionEnVista */
export const proyectosEnVista = planEnTramitacionEnVista;

/** @deprecated Use planEnTramitacionEnVista */
export const ambitosProyectosEnVista = planEnTramitacionEnVista;
