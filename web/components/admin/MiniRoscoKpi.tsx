const TRACK = "#e2e8f0";

export function MiniRosco({
  value,
  total,
  color,
  size = 64,
}: {
  value: number;
  total: number;
  color: string;
  size?: number;
}) {
  const stroke = size >= 72 ? 7 : 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const ratio = total > 0 ? Math.min(1, Math.max(0, value / total)) : 0;
  const filled = ratio * c;
  const pct = Math.round(ratio * 100);
  const mid = size / 2;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden
      className="shrink-0"
    >
      <circle cx={mid} cy={mid} r={r} fill="none" stroke={TRACK} strokeWidth={stroke} />
      {ratio > 0 ? (
        <circle
          cx={mid}
          cy={mid}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={`${filled} ${Math.max(0, c - filled)}`}
          strokeLinecap={ratio > 0.02 && ratio < 0.98 ? "round" : "butt"}
          transform={`rotate(-90 ${mid} ${mid})`}
        />
      ) : null}
      <text
        x={mid}
        y={mid}
        textAnchor="middle"
        dominantBaseline="central"
        fill="#0f172a"
        fontSize={size >= 72 ? 15 : 13}
        fontWeight={650}
      >
        {pct}%
      </text>
    </svg>
  );
}

export function MiniRoscoKpi({
  label,
  value,
  total,
  hint,
  color,
  featured = false,
}: {
  label: string;
  value: number;
  total: number;
  hint: string;
  color: string;
  featured?: boolean;
}) {
  return (
    <div
      className={
        featured
          ? "flex items-center gap-4 rounded-2xl border border-[var(--portal-accent)]/25 bg-[var(--portal-accent-soft)] p-4 shadow-sm ring-1 ring-[var(--portal-accent)]/10"
          : "flex items-center gap-3 rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/[0.03]"
      }
    >
      <MiniRosco value={value} total={total} color={color} size={featured ? 76 : 64} />
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
        <p className="mt-0.5 text-xl font-semibold tabular-nums tracking-tight text-slate-900">
          {value.toLocaleString("es-ES")}
          <span className="ml-1 text-sm font-medium text-slate-400">/ {total.toLocaleString("es-ES")}</span>
        </p>
        <p className="mt-0.5 text-xs leading-snug text-slate-500">{hint}</p>
      </div>
    </div>
  );
}
