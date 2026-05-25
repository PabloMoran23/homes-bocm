"use client";

import { PeriodToggle } from "@/components/madrid/dashboard/PeriodToggle";
import {
  formatPctChange,
  type LicenciasKpiPeriod,
  type LicenciasKpiSnapshot,
} from "@/lib/licencias-dashboard-kpi";

function pctTone(pct: number | null): string {
  if (pct == null || !Number.isFinite(pct)) return "text-slate-400";
  if (pct > 0) return "text-emerald-700";
  if (pct < 0) return "text-rose-700";
  return "text-slate-500";
}

export function LicenciasKpiCard({
  label,
  hint,
  snapshot,
  period,
  onPeriodChange,
}: {
  label: string;
  hint: string;
  snapshot: LicenciasKpiSnapshot | null;
  period: LicenciasKpiPeriod;
  onPeriodChange: (p: LicenciasKpiPeriod) => void;
}) {
  const value = snapshot?.value ?? 0;
  const pct = snapshot?.pctChange ?? null;

  return (
    <div className="relative flex min-h-[7.75rem] flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.03]">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
        <PeriodToggle value={period} onChange={onPeriodChange} />
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
            "Sin datos mensuales"
          )}
        </p>
        <p
          className={`shrink-0 text-sm font-semibold tabular-nums ${pctTone(pct)}`}
          title={
            snapshot
              ? `${formatPctChange(pct)} respecto a ${snapshot.compareLabel}`
              : undefined
          }
        >
          {formatPctChange(pct)}
        </p>
      </div>
    </div>
  );
}
