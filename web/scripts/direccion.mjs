/** Normalización de direcciones del open data de Madrid (número con ceros a la izquierda). */

export function formatNumeroVia(raw) {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  if (/^\d+$/.test(s)) {
    const n = Number(s);
    return n === 0 ? null : String(n);
  }
  return s;
}

export function normalizeDireccion(raw) {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  return s.replace(/\b0+(\d+)\b/g, "$1");
}

export function buildDireccion(row) {
  if (row.direccion) return normalizeDireccion(row.direccion);
  const via = [row.tipo_via, row.nombre_via, formatNumeroVia(row.nmero)]
    .filter(Boolean)
    .join(" ")
    .trim();
  return via || null;
}
