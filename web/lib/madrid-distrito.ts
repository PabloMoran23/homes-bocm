/** Clave normalizada para cruzar nombres de distrito (licencias, SIGMA, mapa). */
export function normDistritoKey(name: string): string {
  return String(name ?? "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/-/g, " ");
}

export function formatDistritoLabel(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => (w.length <= 2 ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");
}
