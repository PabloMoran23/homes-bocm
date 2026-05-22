"use client";

const selectClass =
  "rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition focus:border-[var(--portal-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--portal-accent)]/20";

export function YearRangeControls({
  years,
  from,
  to,
  onFromChange,
  onToChange,
  extra,
}: {
  years: number[];
  from: number;
  to: number;
  onFromChange: (y: number) => void;
  onToChange: (y: number) => void;
  extra?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
      <label className="flex items-center gap-1.5 font-medium">
        Desde
        <select className={selectClass} value={from} onChange={(e) => onFromChange(Number(e.target.value))}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-1.5 font-medium">
        Hasta
        <select className={selectClass} value={to} onChange={(e) => onToChange(Number(e.target.value))}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>
      {extra}
    </div>
  );
}
