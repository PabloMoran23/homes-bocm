"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo, useState, useCallback } from "react";
import { DashboardSection } from "@/components/madrid/dashboard/DashboardSection";
import { DonutChart } from "@/components/madrid/dashboard/DonutChart";
import { SigmaDashboardFiltersBar } from "@/components/madrid/dashboard/SigmaDashboardFiltersBar";
import { SigmaKpiCard } from "@/components/madrid/dashboard/SigmaKpiCard";
import { SigmaDatosNota } from "@/components/madrid/dashboard/SigmaDatosNota";
import { useSigmaFilterRows } from "@/components/madrid/dashboard/useSigmaFilterRows";
import { YearEvolutionChart } from "@/components/madrid/dashboard/YearEvolutionChart";
import { SigmaPromotoresTable } from "@/components/madrid/dashboard/SigmaPromotoresTable";
import { buildSigmaPromotoresTable } from "@/lib/sigma-promotores-table";
import {
  computeSigmaKpi,
  SIGMA_KPI_LABELS,
  type SigmaKpiPeriod,
} from "@/lib/sigma-dashboard-kpi";
import {
  aggregateSigmaFromRows,
  countActiveSigmaFilters,
  EMPTY_SIGMA_FILTERS,
  filterSigmaRows,
  hasActiveSigmaFilters,
  type SigmaDashboardFilters,
} from "@/lib/sigma-dashboard-filters";
import { sigmaStatsToView } from "@/lib/sigma-dashboard-view";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import type { MadridDashboardStats } from "@/lib/types";
import { trackEvent } from "@/lib/analytics";

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

function fmt(n: number) {
  return n.toLocaleString("es-ES");
}

export function SigmaDashboardTab({
  stats,
}: {
  stats: MadridDashboardStats;
}) {
  const sig = stats.sigma;
  const [sigmaFilters, setSigmaFilters] = useState(EMPTY_SIGMA_FILTERS);
  const [sigmaKpiPeriod, setSigmaKpiPeriod] = useState<SigmaKpiPeriod>("5Y");
  const { data: filterRows, loading: filterLoading, error: filterError } = useSigmaFilterRows();

  const kpiRows = useMemo(() => {
    if (!filterRows) return null;
    return filterSigmaRows(filterRows.rows, sigmaFilters);
  }, [filterRows, sigmaFilters]);

  const sigView = useMemo(() => {
    const base = sigmaStatsToView(sig);
    if (!filterRows || !hasActiveSigmaFilters(sigmaFilters)) return base;
    return aggregateSigmaFromRows(filterRows.rows, sigmaFilters, base);
  }, [sig, filterRows, sigmaFilters]);

  const promotoresTop = useMemo(() => {
    if (!kpiRows) return [];
    const labels = new Map(
      (filterRows?.options.promotores ?? []).map((o) => [o.id, o.label]),
    );
    return buildSigmaPromotoresTable(kpiRows, labels, 7);
  }, [kpiRows, filterRows]);

  const handleSigmaFiltersChange = useCallback((next: SigmaDashboardFilters) => {
    setSigmaFilters(next);
    if (hasActiveSigmaFilters(next)) {
      trackEvent("estadisticas_filtro", {
        tab: "sigma",
        activos: countActiveSigmaFilters(next),
      });
    }
  }, []);

  return (
    <>
      <SigmaDashboardFiltersBar
        filterData={filterRows}
        filters={sigmaFilters}
        onChange={handleSigmaFiltersChange}
        filteredCount={sigView.total}
        loading={filterLoading}
        error={filterError}
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,17rem)_1fr] lg:items-stretch">
        <div className="flex flex-col gap-3">
          {(["totales", "vivienda", "urbanismo"] as const).map((metric) => {
            const meta = SIGMA_KPI_LABELS[metric];
            return (
              <SigmaKpiCard
                key={metric}
                label={meta.label}
                hint={meta.hint}
                snapshot={kpiRows ? computeSigmaKpi(kpiRows, metric, sigmaKpiPeriod) : null}
                period={sigmaKpiPeriod}
                onPeriodChange={setSigmaKpiPeriod}
              />
            );
          })}
        </div>
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-slate-500">
              Incoaciones por año del expediente
              {hasActiveSigmaFilters(sigmaFilters) ? " · datos filtrados" : ""}
            </p>
          </div>
          <YearEvolutionChart
            title="Evolución total"
            series={sigView.seriesByYear.map((s) => ({ year: s.year, value: s.count }))}
            valueLabel="proyectos"
            color="#6d28d9"
            height={400}
          />
        </div>
      </div>

      <DashboardSection
        title="Detalle"
        description="Principales promotores según la ficha municipal y desglose por tipo de obra, escala y fase del clasificador."
      >
        <SigmaPromotoresTable rows={promotoresTop} />
        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <DonutChart
            title="Tipo de obra"
            items={sigView.byTipoObra}
            maxItems={8}
            valueLabel="expedientes"
          />
          <DonutChart title="Escala" items={sigView.byEscala} maxItems={8} valueLabel="expedientes" />
          <DonutChart
            title="Fase"
            items={sigView.byFaseNormalizada}
            maxItems={8}
            valueLabel="expedientes"
          />
        </div>
      </DashboardSection>

      <DashboardSection
        title="Distribución territorial"
        description={
          hasActiveSigmaFilters(sigmaFilters)
            ? "Distritos según proyectos filtrados (distrito declarado en la ficha municipal)."
            : "Distritos según ubicación declarada en la ficha de cada proyecto."
        }
      >
        <DistritosCountMap
          title="Distritos"
          items={sigView.byDistrito}
          centroids={stats.distritoCentroids}
          valueLabel="expedientes"
        />
      </DashboardSection>

      {sig.topViviendas.length > 0 ? (
        <section className="mt-8 overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.03]">
          <div className="border-b border-slate-100 bg-gradient-to-br from-slate-50/90 to-white px-5 py-4">
            <h2 className="text-lg font-semibold text-slate-900">Mayor densificación (métricas PDF)</h2>
            <p className="mt-1 text-xs text-slate-500">
              Solo expedientes con estudio parseado; no se recalcula con los filtros de clasificación.
            </p>
          </div>
          <ul className="divide-y divide-slate-100 px-5">
            {sig.topViviendas.map((row) => (
              <li
                key={row.expedienteGrupo}
                className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
              >
                <Link
                  href={sigmaFichaPath(row.expedienteGrupo)}
                  className="font-medium text-[var(--portal-accent)] hover:underline"
                >
                  {row.expedienteGrupo}
                </Link>
                <span className="tabular-nums text-slate-600">
                  {fmt(row.viviendas)} viv.
                  {row.supM2 != null ? ` · ${fmt(Math.round(row.supM2))} m²` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
