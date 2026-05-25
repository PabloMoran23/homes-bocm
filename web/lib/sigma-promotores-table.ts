import {
  sigmaRowIsUrbanismo,
  sigmaRowIsVivienda,
} from "@/lib/sigma-dashboard-kpi";
import type { SigmaFilterRow } from "@/lib/sigma-dashboard-filters";

export type SigmaPromotorTableRow = {
  id: string;
  label: string;
  total: number;
  vivienda: number;
  urbanismo: number;
  privada: number;
  municipal: number;
};

function formatPromotorLabel(id: string): string {
  return id
    .split(/\s+/)
    .map((w) => {
      if (w.length <= 4 && /^[a-z.]+$/i.test(w)) return w.toUpperCase();
      return w.charAt(0).toUpperCase() + w.slice(1);
    })
    .join(" ");
}

/**
 * Top promotores por volumen con desglose de variables (visor + clasificación).
 */
export function buildSigmaPromotoresTable(
  rows: SigmaFilterRow[],
  labelById?: Map<string, string>,
  topN = 7,
): SigmaPromotorTableRow[] {
  const acc = new Map<string, SigmaPromotorTableRow>();

  for (const r of rows) {
    if (!r.pr) continue;
    let row = acc.get(r.pr);
    if (!row) {
      row = {
        id: r.pr,
        label: labelById?.get(r.pr) ?? formatPromotorLabel(r.pr),
        total: 0,
        vivienda: 0,
        urbanismo: 0,
        privada: 0,
        municipal: 0,
      };
      acc.set(r.pr, row);
    }
    row.total += 1;
    if (sigmaRowIsVivienda(r)) row.vivienda += 1;
    if (sigmaRowIsUrbanismo(r)) row.urbanismo += 1;
    if (r.i === "privada") row.privada += 1;
    if (r.i === "municipal") row.municipal += 1;
  }

  return [...acc.values()]
    .sort((a, b) => b.total - a.total || a.label.localeCompare(b.label, "es"))
    .slice(0, topN);
}
