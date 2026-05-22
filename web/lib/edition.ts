/**
 * Edición de producto: qué rutas y datos se publican.
 *
 * - `public`: MVP Madrid (mapa, boletín por zona, fichas, estadísticas)
 * - `full`: desarrollo interno (todas las rutas)
 *
 * Producción sin variable → `public`. Desarrollo local → `full` salvo override.
 */
export type ProductEdition = "public" | "full";

const EDITION_ENV = "NEXT_PUBLIC_EDITION";

export function getEdition(): ProductEdition {
  const raw = process.env[EDITION_ENV];
  if (raw === "public" || raw === "full") return raw;
  if (process.env.NODE_ENV === "development") return "full";
  return "public";
}

export function isPublicEdition(): boolean {
  return getEdition() === "public";
}

/** Rutas accesibles en edición pública (prefijos). */
export const PUBLIC_ROUTE_PREFIXES = [
  "/",
  "/explore",
  "/boletin",
  "/ubicacion",
  "/sigma",
  "/proyecto",
  "/madrid/estadisticas",
  "/estadisticas",
  "/en-desarrollo",
] as const;

/** Prefijos bloqueados en público → página «en desarrollo». */
export const DEV_ONLY_ROUTE_PREFIXES = [
  "/planes",
  "/admin",
  "/fuentes",
  "/madrid/bocm",
  "/madrid/sigma",
  "/madrid/licencias",
  "/api/admin",
] as const;

export function isPublicRoute(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_ROUTE_PREFIXES.some(
    (prefix) => prefix !== "/" && (pathname === prefix || pathname.startsWith(`${prefix}/`)),
  );
}

export function isDevOnlyRoute(pathname: string): boolean {
  return DEV_ONLY_ROUTE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function isRouteAllowedInEdition(pathname: string, edition: ProductEdition): boolean {
  if (edition === "full") return true;
  if (pathname.startsWith("/_next") || pathname.startsWith("/data")) return true;
  if (pathname === "/en-desarrollo") return true;
  if (isDevOnlyRoute(pathname)) return false;
  return isPublicRoute(pathname);
}

/** API permitidas en edición pública. */
export function isPublicApiRoute(pathname: string): boolean {
  return (
    pathname === "/api/nti-asset" ||
    pathname.startsWith("/api/nti-asset/") ||
    pathname === "/api/boletin-area" ||
    pathname.startsWith("/api/boletin-area/") ||
    pathname === "/api/geocode-address" ||
    pathname.startsWith("/api/geocode-address/")
  );
}

export function editionLabel(edition: ProductEdition): string {
  return edition === "public" ? "Madrid (beta)" : "Desarrollo";
}
