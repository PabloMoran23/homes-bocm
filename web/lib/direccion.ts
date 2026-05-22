/** Normalización de direcciones del open data de Madrid (número con ceros a la izquierda). */

export function formatNumeroVia(raw: unknown): string | null {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  if (/^\d+$/.test(s)) {
    const n = Number(s);
    return n === 0 ? null : String(n);
  }
  return s;
}

export function normalizeDireccion(raw: unknown): string | null {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  return s.replace(/\b0+(\d+)\b/g, "$1");
}
