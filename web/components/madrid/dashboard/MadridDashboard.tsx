"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo, useState } from "react";
import { DonutChart } from "@/components/madrid/dashboard/DonutChart";

const DistritosCountMap = dynamic(
  () =>
    import("@/components/madrid/dashboard/DistritosCountMap").then((m) => m.DistritosCountMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[380px] animate-pulse items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-sm text-slate-400">
        Cargando mapa…
      </div>
    ),
  },
);
import { DashboardSection } from "@/components/madrid/dashboard/DashboardSection";
import { DashboardFiltersBar } from "@/components/madrid/dashboard/DashboardFiltersBar";
import { LicenciasDatosNota } from "@/components/madrid/dashboard/LicenciasDatosNota";
import { useLicenciasFilterRows } from "@/components/madrid/dashboard/useLicenciasFilterRows";
import {
  aggregateLicenciasFromRows,
  EMPTY_LICENCIAS_FILTERS,
  hasActiveLicenciasFilters,
} from "@/lib/licencias-dashboard-filters";
import { LicenciasKpiCard } from "@/components/madrid/dashboard/LicenciasKpiCard";
import { GranularityToggle } from "@/components/madrid/dashboard/GranularityToggle";
import {
  computeLicenciasKpi,
  LICENCIAS_KPI_LABELS,
  type LicenciasKpiPeriod,
} from "@/lib/licencias-dashboard-kpi";
import { ActuacionQueLineChart } from "@/components/madrid/dashboard/ActuacionQueLineChart";
import { YearEvolutionChart } from "@/components/madrid/dashboard/YearEvolutionChart";
import { SigmaDashboardTab } from "@/components/madrid/dashboard/SigmaDashboardTab";
import type { LicenciasTimeGranularity, MadridDashboardStats } from "@/lib/types";

type Tab = "licencias" | "sigma";

function fmt(n: number) {
  return n.toLocaleString("es-ES");
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("es-ES", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function MadridDashboard({ stats }: { stats: MadridDashboardStats }) {
  const [tab, setTab] = useState<Tab>("licencias");
  const [licGranularity, setLicGranularity] = useState<LicenciasTimeGranularity>("month");
  const [licKpiPeriod, setLicKpiPeriod] = useState<LicenciasKpiPeriod>("1Y");
  const [licFilters, setLicFilters] = useState(EMPTY_LICENCIAS_FILTERS);
  const { data: filterRows, loading: filterRowsLoading, error: filterRowsError } =
    useLicenciasFilterRows();
  const lic = stats.licencias;
  const sig = stats.sigma;

  const licView = useMemo(() => {
    if (!lic) return null;
    if (!filterRows || !hasActiveLicenciasFilters(licFilters)) return lic;
    return aggregateLicenciasFromRows(filterRows.rows, licFilters, lic);
  }, [lic, filterRows, licFilters]);

  const licenciasCount = licView?.totalRows ?? lic?.totalRows ?? 0;

  return (
    <div className="min-h-full">
      {/* Hero */}
      <div className="border-b border-slate-200/80 bg-gradient-to-br from-[var(--portal-accent-soft)]/40 via-white to-slate-50">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--portal-accent)]">
            Madrid Ciudad
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Estadísticas urbanísticas
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
            Licencias urbanísticas y proyectos de planeamiento en un solo panel.
            Gráficos interactivos con filtro temporal.
          </p>
          <p className="mt-2 text-xs text-slate-400">
            {fmtDate(stats.generatedAt)}
          </p>

          <div className="mt-6 inline-flex rounded-xl border border-slate-200/90 bg-white/80 p-1 shadow-sm backdrop-blur-sm">
            <button
              type="button"
              onClick={() => setTab("licencias")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-all ${
                tab === "licencias"
                  ? "bg-[var(--portal-accent)] text-white shadow-md shadow-teal-900/15"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              Licencias
            </button>
            <button
              type="button"
              onClick={() => setTab("sigma")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-all ${
                tab === "sigma"
                  ? "bg-[var(--portal-accent)] text-white shadow-md shadow-teal-900/15"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              Proyectos
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="mb-6 flex justify-end">
          <Link
            href="/explore"
            className="inline-flex items-center gap-1 text-sm font-medium text-[var(--portal-accent)] hover:underline"
          >
            Ver mapa explorar
            <span aria-hidden>→</span>
          </Link>
        </div>

        {tab === "licencias" && lic && licView ? (
          <>
            <LicenciasDatosNota />
            <DashboardFiltersBar
              filterData={filterRows}
              filters={licFilters}
              onChange={setLicFilters}
              filteredCount={licenciasCount}
              loading={filterRowsLoading}
              error={filterRowsError}
            />
            <div className="grid gap-5 lg:grid-cols-[minmax(0,17rem)_1fr] lg:items-stretch">
              <div className="flex flex-col gap-3">
                {(["volumen", "obras", "vivienda"] as const).map((metric) => {
                  const meta = LICENCIAS_KPI_LABELS[metric];
                  return (
                    <LicenciasKpiCard
                      key={metric}
                      label={meta.label}
                      hint={meta.hint}
                      snapshot={computeLicenciasKpi(licView, metric, licKpiPeriod)}
                      period={licKpiPeriod}
                      onPeriodChange={setLicKpiPeriod}
                    />
                  );
                })}
              </div>
              <div className="min-w-0">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-slate-500">
                    {licGranularity === "year"
                      ? "Vista anual del dataset."
                      : "Vista mensual según fecha de concesión."}
                    {hasActiveLicenciasFilters(licFilters) ? " · datos filtrados" : ""}
                  </p>
                  <GranularityToggle value={licGranularity} onChange={setLicGranularity} />
                </div>
                <YearEvolutionChart
                  title="Evolución total"
                  series={licView.seriesByYear.map((s) => ({ year: s.year, value: s.total }))}
                  seriesByMonth={licView.seriesByMonth}
                  granularity={licGranularity}
                  valueLabel="licencias"
                  height={400}
                />
              </div>
            </div>

            {(licView.seriesByYearActuacionQue?.length ??
            licView.seriesByMonthActuacionQue?.length) ? (
              <DashboardSection
                title="Qué se va a hacer"
                description="Desglose por actuación prevista desde 2023 (etiquetado del Ayuntamiento más homogéneo)."
              >
                <div className="mb-4 flex flex-wrap items-center justify-end gap-3">
                  <GranularityToggle value={licGranularity} onChange={setLicGranularity} />
                </div>
                <ActuacionQueLineChart
                  title="Actuaciones por tipo"
                  seriesByYear={licView.seriesByYearActuacionQue ?? []}
                  seriesByMonth={licView.seriesByMonthActuacionQue}
                  granularity={licGranularity}
                  cutFromOrdenanza
                />
              </DashboardSection>
            ) : null}

            <DashboardSection
              title="Distribución"
              description={
                hasActiveLicenciasFilters(licFilters)
                  ? "Composición de las licencias que cumplen los filtros activos."
                  : "Composición global del dataset; distritos en mapa según ubicación de las licencias."
              }
            >
              <div className="flex flex-col gap-5">
                <DistritosCountMap
                  title="Distritos"
                  items={licView.topDistrito}
                  mapPoints={licView.topDistritoMap}
                  valueLabel="licencias"
                />
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  <DonutChart title="Uso del suelo" items={licView.topUso} maxItems={8} valueLabel="licencias" />
                  <DonutChart
                    title="Procedimiento"
                    items={licView.topProcedimiento}
                    maxItems={8}
                    valueLabel="licencias"
                  />
                  {lic.topTipoExpediente.length > 0 && !hasActiveLicenciasFilters(licFilters) ? (
                    <DonutChart
                      title="Tipo de expediente (raw)"
                      items={lic.topTipoExpediente}
                      maxItems={7}
                      valueLabel="licencias"
                    />
                  ) : null}
                </div>
              </div>
            </DashboardSection>
          </>
        ) : null}

        {tab === "licencias" && !lic ? (
          <p className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
            Índice de licencias no disponible. Ejecuta{" "}
            <code className="rounded bg-amber-100/80 px-1.5 py-0.5 text-xs">npm run build-data</code>.
          </p>
        ) : null}

        {tab === "sigma" ? <SigmaDashboardTab stats={stats} /> : null}
      </div>
    </div>
  );
}
