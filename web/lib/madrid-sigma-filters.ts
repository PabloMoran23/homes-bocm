/** Filtros compartidos: catálogo SIGMA ↔ mapa (/madrid/sigma). */

import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";

/** Año mínimo por defecto: actividad estrictamente posterior al calendario 2020 (= desde 01/01/2021 UTC). */
export const SIGMA_DEFAULT_MIN_YEAR_EXCLUSIVE_2020 = 2021;

function toUnixMs(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n) || n <= 0) return null;
  return n;
}

/** Año AAA del código expediente distrito/AAA/secuencia. */
export function expedienteAnioCodigo(numero: string | null | undefined): number | null {
  const exp = String(numero || "").trim();
  const m = exp.match(/^(\d+)\/(\d{4})\//);
  return m ? parseInt(m[2], 10) : null;
}

/**
 * Marco temporal «más reciente» disponible en atributos ArcGIS típicos SIGMA IP/AD,
 * para filtrar por vigencia cronológica.
 */
export function sigmaActivityMs(properties: Record<string, unknown>): number | null {
  const parts = ["FEX_DT_APROB", "FEX_DT_INFOPUB_INI", "FEX_DT_INFOPUB_FIN"].map((k) => toUnixMs(properties[k]));
  const ok = parts.filter((x): x is number => x != null);
  if (ok.length) return Math.max(...ok);

  const y = expedienteAnioCodigo(String(properties.EXP_TX_NUMERO ?? ""));
  if (y != null) return Date.UTC(y, 5, 15);
  return null;
}

/** `minYearInclusive` ej. 2021 → fecha límite 1 enero 2021 00:00 UTC. */
export function sigmaPassesMinYearInclusive(props: Record<string, unknown>, minYearInclusive: number): boolean {
  const thresh = Date.UTC(minYearInclusive, 0, 1);
  const ms = sigmaActivityMs(props);
  if (ms != null) return ms >= thresh;
  const y = expedienteAnioCodigo(String(props.EXP_TX_NUMERO ?? ""));
  if (y != null) return y >= minYearInclusive;
  return false;
}

export function sigmaPassesPortalLink(
  properties: Record<string, unknown>,
  bocmByExpediente: Record<string, unknown[]> | null | undefined,
): boolean {
  if (!bocmByExpediente) return false;
  const raw = properties.EXP_TX_NUMERO;
  if (raw == null || String(raw).trim() === "") return false;
  const g = expedienteGrupoKeyFromVariant(String(raw));
  const row = bocmByExpediente[g];
  return Array.isArray(row) && row.length > 0;
}
