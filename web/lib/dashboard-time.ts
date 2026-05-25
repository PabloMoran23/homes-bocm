import type { LicenciasTimeGranularity } from "@/lib/types";

const MONTH_SHORT = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sep",
  "oct",
  "nov",
  "dic",
];

/** `2024-03` → `mar 24` */
export function formatMonthLabel(monthKey: string): string {
  const [y, m] = monthKey.split("-");
  const mi = Number(m) - 1;
  if (!y || mi < 0 || mi > 11) return monthKey;
  return `${MONTH_SHORT[mi]} ${y.slice(2)}`;
}

export function monthInYearRange(monthKey: string, fromYear: number, toYear: number): boolean {
  const y = Number(monthKey.slice(0, 4));
  return y >= fromYear && y <= toYear;
}

/** Comparación lexicográfica válida para claves `YYYY-MM`. */
export function monthOnOrAfter(monthKey: string, minMonthKey: string): boolean {
  return monthKey >= minMonthKey;
}

export function monthInDetailRange(
  monthKey: string,
  fromYear: number,
  toYear: number,
  minMonthKey: string,
): boolean {
  if (!monthOnOrAfter(monthKey, minMonthKey)) return false;
  return monthInYearRange(monthKey, fromYear, toYear);
}

export function yearsFromMonths(months: string[]): number[] {
  const set = new Set<number>();
  for (const m of months) {
    const y = Number(m.slice(0, 4));
    if (Number.isFinite(y)) set.add(y);
  }
  return [...set].sort((a, b) => a - b);
}

export function granularityLabel(g: LicenciasTimeGranularity): string {
  return g === "year" ? "años" : "meses";
}
