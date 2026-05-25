"use client";

import {
  countActiveLicenciasFilters,
  EMPTY_LICENCIAS_FILTERS,
  hasActiveLicenciasFilters,
  type LicenciasDashboardFilters,
  type LicenciasFilterOption,
  type LicenciasFilterRowsFile,
} from "@/lib/licencias-dashboard-filters";
import { DashboardFiltersShell } from "@/components/madrid/dashboard/DashboardFiltersShell";

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
  options: LicenciasFilterOption[];
  onChange: (id: string) => void;
}) {
  if (!options.length) return null;

  return (
    <label className="block min-w-0 flex-1 sm:min-w-[9.5rem] sm:max-w-[15rem]">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={SELECT_CLASS}
      >
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

export function DashboardFiltersBar({
  filterData,
  filters,
  onChange,
  filteredCount,
  loading,
  error,
}: {
  filterData: LicenciasFilterRowsFile | null;
  filters: LicenciasDashboardFilters;
  onChange: (f: LicenciasDashboardFilters) => void;
  filteredCount: number;
  loading?: boolean;
  error?: boolean;
}) {
  const active = countActiveLicenciasFilters(filters);

  if (error) {
    return (
      <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Filtros no disponibles. Ejecuta{" "}
        <code className="rounded bg-amber-100/80 px-1 text-xs">npm run build-data</code> para generar{" "}
        <code className="rounded bg-amber-100/80 px-1 text-xs">madrid-licencias-filter-rows.json</code>.
      </div>
    );
  }

  const totalHint =
    hasActiveLicenciasFilters(filters) && filterData
      ? ` de ${filterData.totalRows.toLocaleString("es-ES")}`
      : undefined;

  return (
    <DashboardFiltersShell
      subtitle="Madrid capital"
      activeCount={active}
      filteredCount={filteredCount}
      countLabel="licencias"
      totalHint={totalHint}
      loading={loading}
      onClear={active > 0 ? () => onChange(EMPTY_LICENCIAS_FILTERS) : undefined}
    >
      {filterData && !loading ? (
        <div className="grid grid-cols-2 gap-x-3 gap-y-3 sm:flex sm:flex-wrap sm:gap-x-4">
          <FilterSelect
            label="Distrito"
            placeholder="Todos"
            value={filters.distritos[0] ?? ""}
            options={filterData.options.distritos}
            onChange={(id) => onChange({ ...filters, distritos: id ? [id] : [] })}
          />
          <FilterSelect
            label="Actuación"
            placeholder="Todas"
            value={filters.actuaciones[0] ?? ""}
            options={filterData.options.actuaciones}
            onChange={(id) => onChange({ ...filters, actuaciones: id ? [id] : [] })}
          />
          <FilterSelect
            label="Procedimiento"
            placeholder="Todos"
            value={filters.procedimientos[0] ?? ""}
            options={filterData.options.procedimientos}
            onChange={(id) => onChange({ ...filters, procedimientos: id ? [id] : [] })}
          />
          <FilterSelect
            label="Uso"
            placeholder="Todos"
            value={filters.usos[0] ?? ""}
            options={filterData.options.usos}
            onChange={(id) => onChange({ ...filters, usos: id ? [id] : [] })}
          />
        </div>
      ) : null}
    </DashboardFiltersShell>
  );
}
