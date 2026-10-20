"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  ANALYTICS_RANGES,
  ANALYTICS_SECTIONS,
  ANALYTICS_SOURCES,
  ANALYTICS_TRAFFIC,
  SECTION_LABELS,
  SOURCE_LABELS,
  TRAFFIC_LABELS,
  analyticsHref,
  rangeLabel,
  type AnalyticsSelection,
} from "@/lib/analytics-filters";

export function AnalyticsFilters({ value, preview = false }: { value: AnalyticsSelection; preview?: boolean }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function go(next: Partial<AnalyticsSelection>) {
    const href = analyticsHref({ ...value, ...next }, preview);
    startTransition(() => {
      router.push(href, { scroll: false });
    });
  }

  return (
    <form
      className={`rounded-2xl border border-[rgba(42,38,34,0.08)] bg-white/90 p-3 shadow-sm backdrop-blur ${pending ? "opacity-80" : ""}`}
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="sr-only">Periodo</span>
        {ANALYTICS_RANGES.map((range) => {
          const active = value.range === range;
          return (
            <button
              key={range}
              type="button"
              aria-pressed={active}
              onClick={() => go({ range })}
              className={
                active
                  ? "rounded-full bg-[var(--portal-accent)] px-3 py-1.5 text-sm font-semibold text-white"
                  : "rounded-full bg-[var(--portal-paper-deep)] px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-[var(--portal-accent-soft)]"
              }
            >
              {rangeLabel(range)}
            </button>
          );
        })}
        <span className="ml-auto text-xs text-slate-500" aria-live="polite">
          {pending ? "Actualizando…" : "Hora de Madrid"}
        </span>
      </div>
      {value.range === "custom" ? (
        <div className="mt-3 flex flex-wrap gap-3">
          <label className="text-xs font-medium text-slate-600">
            Desde
            <input
              type="date"
              value={value.fromDate}
              max={value.toDate}
              onChange={(event) => go({ range: "custom", fromDate: event.target.value })}
              className="mt-1 block rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900"
            />
          </label>
          <label className="text-xs font-medium text-slate-600">
            Hasta
            <input
              type="date"
              value={value.toDate}
              min={value.fromDate}
              onChange={(event) => go({ range: "custom", toDate: event.target.value })}
              className="mt-1 block rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900"
            />
          </label>
        </div>
      ) : null}
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <FilterSelect
          label="Tráfico"
          value={value.traffic}
          options={ANALYTICS_TRAFFIC.map((id) => ({ id, label: TRAFFIC_LABELS[id] }))}
          onChange={(traffic) => go({ traffic: traffic as AnalyticsSelection["traffic"] })}
        />
        <FilterSelect
          label="Origen"
          value={value.source}
          options={ANALYTICS_SOURCES.map((id) => ({ id, label: SOURCE_LABELS[id] }))}
          onChange={(source) => go({ source: source as AnalyticsSelection["source"] })}
        />
        <FilterSelect
          label="Sección"
          value={value.section}
          options={ANALYTICS_SECTIONS.map((id) => ({ id, label: SECTION_LABELS[id] }))}
          onChange={(section) => go({ section: section as AnalyticsSelection["section"] })}
        />
      </div>
    </form>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { id: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-xs font-medium text-slate-600">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-slate-900"
      >
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
