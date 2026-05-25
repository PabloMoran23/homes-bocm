"use client";

import { useMemo } from "react";
import {
  buildSigmaAnioOptions,
  countActiveSigmaFilters,
  EMPTY_SIGMA_FILTERS,
  hasActiveSigmaFilters,
  type SigmaDashboardFilters,
  type SigmaFilterOption,
  type SigmaFilterRowsFile,
} from "@/lib/sigma-dashboard-filters";
import { DashboardFiltersShell } from "@/components/madrid/dashboard/DashboardFiltersShell";
import { SIGMA_DASHBOARD_PRIMARY_AXES } from "@/lib/sigma-dashboard-constants";

const SELECT_CLASS =
  "w-full rounded-md border border-slate-200 bg-white px-2.5 py-2 text-sm text-slate-800 outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25";

function FilterSelect({
  label,
  placeholder,
  value,
  options,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: string;
  options: SigmaFilterOption[];
  onChange: (id: string) => void;
}) {
  if (!options.length) return null;

  return (
    <label className="block min-w-0 flex-1 sm:min-w-[9.5rem] sm:max-w-[15rem]">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={SELECT_CLASS}>
        <option value="">{placeholder}</option>
        {options.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {opt.label} ({opt.count.toLocaleString("es-ES")})
          </option>
        ))}
      </select>
    </label>
  );
}

export function SigmaDashboardFiltersBar({
  filterData,
  filters,
  onChange,
  filteredCount,
  loading,
  error,
}: {
  filterData: SigmaFilterRowsFile | null;
  filters: SigmaDashboardFilters;
  onChange: (f: SigmaDashboardFilters) => void;
  filteredCount: number;
  loading?: boolean;
  error?: boolean;
}) {
  const active = countActiveSigmaFilters(filters);
  const anioOptions = useMemo(
    () => (filterData ? buildSigmaAnioOptions(filterData.rows) : []),
    [filterData],
  );

  if (error) {
    return (
      <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Filtros de proyectos no disponibles. Ejecuta{" "}
        <code className="rounded bg-amber-100/80 px-1 text-xs">npm run build-data</code> para generar{" "}
        <code className="rounded bg-amber-100/80 px-1 text-xs">madrid-sigma-filter-rows.json</code>.
      </div>
    );
  }

  const totalHint =
    hasActiveSigmaFilters(filters) && filterData
      ? ` de ${filterData.totalRows.toLocaleString("es-ES")}`
      : undefined;

  return (
    <DashboardFiltersShell
      subtitle="Año de incoación y clasificación automática"
      activeCount={active}
      filteredCount={filteredCount}
      countLabel="expedientes"
      totalHint={totalHint}
      loading={loading}
      onClear={active > 0 ? () => onChange(EMPTY_SIGMA_FILTERS) : undefined}
    >
      {filterData && !loading ? (
        <div className="grid grid-cols-2 gap-x-3 gap-y-3 sm:flex sm:flex-wrap sm:gap-x-4">
          <FilterSelect
            label="Año"
            placeholder="Todos"
            value={filters.anio[0] ?? ""}
            options={anioOptions}
            onChange={(id) => onChange({ ...filters, anio: id ? [id] : [] })}
          />
          {SIGMA_DASHBOARD_PRIMARY_AXES.map((axis) => (
            <FilterSelect
              key={axis.id}
              label={axis.label}
              placeholder="Todos"
              value={filters[axis.id][0] ?? ""}
              options={filterData.options[axis.id]}
              onChange={(id) => onChange({ ...filters, [axis.id]: id ? [id] : [] })}
            />
          ))}
          <FilterSelect
            label="Distrito"
            placeholder="Todos"
            value={filters.distrito[0] ?? ""}
            options={filterData.options.distritos}
            onChange={(id) => onChange({ ...filters, distrito: id ? [id] : [] })}
          />
          <FilterSelect
            label="Iniciativa"
            placeholder="Todas"
            value={filters.iniciativa[0] ?? ""}
            options={filterData.options.iniciativas}
            onChange={(id) => onChange({ ...filters, iniciativa: id ? [id] : [] })}
          />
        </div>
      ) : null}
    </DashboardFiltersShell>
  );
}
