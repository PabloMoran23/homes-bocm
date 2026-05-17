/** Normaliza nº expediente Ayuntamiento tipo D/A/N al grupo con último tramo 5 dígitos (coincide con build-data). */

export function normExpediente(num: unknown): string {
  return String(num ?? "")
    .trim()
    .replace(/\s+/g, "");
}

export function expedienteGrupoKeyFromVariant(raw: string): string {
  const n = normExpediente(raw);
  const parts = n.split("/");
  if (parts.length === 3 && /^\d+$/.test(parts[2])) {
    return `${parts[0]}/${parts[1]}/${parts[2].padStart(5, "0")}`;
  }
  return n;
}
