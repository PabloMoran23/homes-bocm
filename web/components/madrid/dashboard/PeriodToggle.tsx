"use client";

import type { LicenciasKpiPeriod } from "@/lib/licencias-dashboard-kpi";

export function PeriodToggle({
  value,
  onChange,
}: {
  value: LicenciasKpiPeriod;
  onChange: (p: LicenciasKpiPeriod) => void;
}) {
  return (
    <div
      className="inline-flex rounded-lg border border-slate-200 bg-slate-100/80 p-0.5 shadow-inner"
      role="group"
      aria-label="Periodo del indicador"
    >
      {(
        [
          { id: "1M" as const, label: "1M" },
          { id: "1Y" as const, label: "1Y" },
        ] as const
      ).map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          aria-pressed={value === id}
          className={`min-w-[2.25rem] rounded-md px-2 py-1 text-[11px] font-bold tracking-wide transition-all ${
            value === id
              ? "bg-white text-[var(--portal-accent)] shadow-sm"
              : "text-slate-500 hover:text-slate-800"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
