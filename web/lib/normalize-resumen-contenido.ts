/** Normaliza resumenContenido del visor municipal (espacios, trim). */
export function normalizeResumenContenido(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const s = value.trim().replace(/\s+/g, " ");
  return s || null;
}

export function resumenContenidoFromVisorFicha(
  ficha: { resumenContenido?: string | null } | null | undefined,
): string | null {
  return normalizeResumenContenido(ficha?.resumenContenido);
}
