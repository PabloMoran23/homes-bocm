export function KpiCard({
  label,
  value,
  hint,
  accent = "teal",
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: "teal" | "sky" | "amber";
}) {
  const accentBar = {
    teal: "bg-[var(--portal-accent)]",
    sky: "bg-sky-500",
    amber: "bg-amber-500",
  }[accent];

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.03]">
      <div className={`absolute left-0 top-0 h-full w-1 ${accentBar}`} />
      <p className="pl-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className="mt-1.5 pl-2 text-2xl font-semibold tabular-nums tracking-tight text-slate-900">
        {value}
      </p>
      {hint ? (
        <p className="mt-1.5 pl-2 text-xs leading-snug text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}
