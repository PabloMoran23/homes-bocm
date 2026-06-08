/**
 * Textos de producto: lenguaje claro para el usuario (sin SIGMA / expediente técnico).
 */
export const PROYECTOS_URBANISTICOS = "Proyectos urbanísticos";
export const PROYECTOS = "Proyectos";
export const PROYECTO = "Proyecto";

export const proyectosEnVista = (n: number) =>
  `${n.toLocaleString("es-ES")} proyecto${n === 1 ? "" : "s"} en vista`;

export const ambitosProyectosEnVista = (n: number) =>
  `${n.toLocaleString("es-ES")} ámbito${n === 1 ? "" : "s"} de proyecto`;
