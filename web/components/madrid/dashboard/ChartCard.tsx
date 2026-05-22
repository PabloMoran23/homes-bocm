import type { ReactNode } from "react";

export function ChartCard({
  title,
  subtitle,
  controls,
  children,
  height = 300,
  className = "",
}: {
  title: string;
  subtitle?: string;
  controls?: ReactNode;
  children: ReactNode;
  height?: number;
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.03] ${className}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 bg-gradient-to-br from-slate-50/90 via-white to-white px-5 py-4">
        <div>
          <h3 className="text-[15px] font-semibold tracking-tight text-slate-900">{title}</h3>
          {subtitle ? (
            <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        {controls ? <div className="flex flex-wrap items-center gap-2">{controls}</div> : null}
      </div>
      <div className="px-3 py-3 sm:px-4" style={{ height }}>
        {children}
      </div>
    </div>
  );
}
