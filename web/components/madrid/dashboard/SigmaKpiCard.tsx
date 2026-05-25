"use client";

import {
  formatPctChange,
  type SigmaKpiPeriod,
  type SigmaKpiSnapshot,
} from "@/lib/sigma-dashboard-kpi";

const SIGMA_PERIOD_OPTIONS = [
  { id: "1Y" as const, label: "1Y" },
  { id: "5Y" as const, label: "5Y" },
];

function pctTone(pct: number | null): string {
  if (pct == null || !Number.isFinite(pct)) return "text-slate-400";
  if (pct > 0) return "text-emerald-700";
  if (pct < 0) return "text-rose-700";
  return "text-slate-500";
}

export function SigmaKpiCard({
  label,
  hint,
  snapshot,
  period,
  onPeriodChange,
}: {
  label: string;
  hint: string;
  snapshot: SigmaKpiSnapshot | null;
  period: SigmaKpiPeriod;
  onPeriodChange: (p: SigmaKpiPeriod) => void;
}) {
  const value = snapshot?.value ?? 0;
  const pct = snapshot?.pctChange ?? null;

  return (
    <div className="relative flex min-h-[7.75rem] flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.03]">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
        <div
          className="inline-flex rounded-lg border border-slate-200 bg-slate-100/80 p-0.5 shadow-inner"
          role="group"
          aria-label="Periodo del indicador"
        >
          {SIGMA_PERIOD_OPTIONS.map(({ id, label: optLabel }) => (
            <button
              key={id}
              type="button"
              onClick={() => onPeriodChange(id)}
              aria-pressed={period === id}
              className={`min-w-[2.25rem] rounded-md px-2 py-1 text-[11px] font-bold tracking-wide transition-all ${
                period === id
                  ? "bg-white text-[var(--portal-accent)] shadow-sm"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              {optLabel}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-slate-900">
        {value.toLocaleString("es-ES")}
      </p>
      <p className="mt-1 text-xs leading-snug text-slate-500">{hint}</p>
      <div className="mt-auto flex items-end justify-between gap-2 pt-3">
        <p className="text-[11px] text-slate-400">
          {snapshot ? (
            <>
              {snapshot.periodLabel}
              <span className="text-slate-300"> · </span>
              vs {snapshot.compareLabel}
            </>
          ) : (
            "Sin datos por año"
          )}
        </p>
        <p
          className={`shrink-0 text-sm font-semibold tabular-nums ${pctTone(pct)}`}
          title={
            snapshot ? `${formatPctChange(pct)} respecto a ${snapshot.compareLabel}` : undefined
          }
        >
          {formatPctChange(pct)}
        </p>
      </div>
    </div>
  );
}
