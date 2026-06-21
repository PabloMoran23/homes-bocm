/** `madrid` = ciudad (prod). `cm` = Comunidad de Madrid + portales municipales (local). */
export type MapScope = "madrid" | "cm";

export function getMapScope(): MapScope {
  const raw = process.env.NEXT_PUBLIC_MAP_SCOPE?.trim().toLowerCase();
  return raw === "cm" ? "cm" : "madrid";
}

export function isCmMapScope(): boolean {
  return getMapScope() === "cm";
}
