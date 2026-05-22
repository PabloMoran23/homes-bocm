"use client";

import type { LicenciasTimeGranularity } from "@/lib/types";

export function GranularityToggle({
  value,
  onChange,
}: {
  value: LicenciasTimeGranularity;
  onChange: (g: LicenciasTimeGranularity) => void;
}) {
  return (
    <div
      className="inline-flex rounded-lg border border-slate-200 bg-slate-100/80 p-0.5 shadow-inner"
      role="group"
      aria-label="Granularidad temporal"
    >
      {(
        [
          { id: "year" as const, label: "Años" },
          { id: "month" as const, label: "Meses" },
        ] as const
      ).map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
            value === id
              ? "bg-white text-[var(--portal-accent)] shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
