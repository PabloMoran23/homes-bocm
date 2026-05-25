"use client";

import { useEffect, useId, useState, type ReactNode } from "react";

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      className={`shrink-0 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}
      aria-hidden
    >
      <path
        d="M5 7.5L10 12.5L15 7.5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function DashboardFiltersShell({
  title = "Filtros",
  subtitle,
  activeCount,
  filteredCount,
  countLabel,
  totalHint,
  loading,
  onClear,
  children,
}: {
  title?: string;
  subtitle?: string;
  activeCount: number;
  filteredCount: number;
  countLabel: string;
  totalHint?: string;
  loading?: boolean;
  onClear?: () => void;
  children: ReactNode;
}) {
  const panelId = useId();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)");
    const sync = () => setOpen(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const countText = loading
    ? "Cargando…"
    : `${filteredCount.toLocaleString("es-ES")} ${countLabel}${totalHint ?? ""}`;

  return (
    <section className="mb-6 rounded-2xl border border-slate-200/90 bg-white p-3 shadow-sm ring-1 ring-slate-900/[0.03] sm:p-5">
      <div className="flex items-start gap-2 sm:items-end sm:justify-between sm:gap-3">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-start gap-2 text-left sm:pointer-events-none sm:cursor-default"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
        >
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
              {activeCount > 0 ? (
                <span className="rounded-full bg-[var(--portal-accent-soft)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--portal-accent)]">
                  {activeCount} activo{activeCount === 1 ? "" : "s"}
                </span>
              ) : null}
            </div>
            <p
              className={`mt-0.5 text-xs text-slate-500 ${open ? "hidden sm:block" : "line-clamp-1 sm:line-clamp-none"}`}
            >
              {subtitle}
            </p>
            <p className="mt-1 text-xs tabular-nums text-slate-500 sm:hidden">{countText}</p>
          </div>
          <span className="shrink-0 pt-0.5 sm:hidden">
            <Chevron open={open} />
          </span>
        </button>

        <div className="hidden shrink-0 flex-wrap items-center gap-2 pb-0.5 sm:flex">
          <span className="text-xs tabular-nums text-slate-500">{countText}</span>
          {activeCount > 0 && onClear ? (
            <button
              type="button"
              onClick={onClear}
              className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Limpiar
            </button>
          ) : null}
        </div>
      </div>

      <div
        id={panelId}
        className={`${open ? "mt-3 block" : "hidden"} sm:mt-4 sm:block`}
      >
        {children}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 sm:hidden">
          <span className="text-xs tabular-nums text-slate-500">{countText}</span>
          {activeCount > 0 && onClear ? (
            <button
              type="button"
              onClick={onClear}
              className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
            >
              Limpiar
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}
