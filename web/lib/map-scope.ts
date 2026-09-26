/** `madrid` = solo la ciudad. `cm` = un municipio cada vez, con portales (producción y `dev:cm`). */
export type MapScope = "madrid" | "cm";

export function getMapScope(): MapScope {
  const raw = process.env.NEXT_PUBLIC_MAP_SCOPE?.trim().toLowerCase();
  return raw === "cm" ? "cm" : "madrid";
}

export function isCmMapScope(): boolean {
  return getMapScope() === "cm";
}
