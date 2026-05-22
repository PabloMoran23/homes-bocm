"use client";

import { useMemo, useState } from "react";
import { Line } from "react-chartjs-2";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { registerDashboardCharts } from "@/components/madrid/dashboard/register-charts";
import { YearRangeControls } from "@/components/madrid/dashboard/YearRangeControls";
import {
  formatMonthLabel,
  granularityLabel,
  monthInYearRange,
  yearsFromMonths,
} from "@/lib/dashboard-time";
import {
  lineChartOptions,
  PORTAL_TEAL,
  PORTAL_TEAL_LIGHT,
} from "@/lib/dashboard-chart-theme";
import type {
  LicenciasTimeGranularity,
  MadridDashboardMonthPoint,
} from "@/lib/types";

registerDashboardCharts();

type YearPoint = { year: number; value: number };

export function YearEvolutionChart({
  title,
  subtitle,
  series,
  seriesByMonth,
  granularity = "year",
  valueLabel = "expedientes",
  color = PORTAL_TEAL,
}: {
  title: string;
  subtitle?: string;
  /** Serie anual (años). */
  series: YearPoint[];
  /** Serie mensual (`YYYY-MM`); obligatoria si `granularity === "month"`. */
  seriesByMonth?: MadridDashboardMonthPoint[];
  granularity?: LicenciasTimeGranularity;
  valueLabel?: string;
  color?: string;
}) {
  const yearSorted = useMemo(
    () => [...series].sort((a, b) => a.year - b.year),
    [series],
  );
  const monthSorted = useMemo(
    () => [...(seriesByMonth ?? [])].sort((a, b) => a.month.localeCompare(b.month)),
    [seriesByMonth],
  );

  const years = useMemo(() => {
    if (granularity === "year") return yearSorted.map((p) => p.year);
    return yearsFromMonths(monthSorted.map((m) => m.month));
  }, [granularity, yearSorted, monthSorted]);

  const minY = years[0] ?? new Date().getFullYear() - 10;
  const maxY = years[years.length - 1] ?? new Date().getFullYear();
  const [from, setFrom] = useState(minY);
  const [to, setTo] = useState(maxY);

  const filtered = useMemo(() => {
    if (granularity === "year") {
      return yearSorted
        .filter((p) => p.year >= from && p.year <= to)
        .map((p) => ({ label: String(p.year), value: p.value }));
    }
    return monthSorted
      .filter((m) => monthInYearRange(m.month, from, to))
      .map((m) => ({ label: formatMonthLabel(m.month), value: m.total }));
  }, [granularity, yearSorted, monthSorted, from, to]);

  const chartData = useMemo(
    () => ({
      labels: filtered.map((p) => p.label),
      datasets: [
        {
          label: title,
          data: filtered.map((p) => p.value),
          borderColor: color,
          backgroundColor: PORTAL_TEAL_LIGHT,
          fill: true,
          tension: granularity === "month" ? 0.25 : 0.35,
          pointRadius: granularity === "month" ? 2 : 4,
          pointHoverRadius: granularity === "month" ? 5 : 6,
          pointBackgroundColor: "#fff",
          pointBorderColor: color,
          pointBorderWidth: 2,
          borderWidth: 2.5,
        },
      ],
    }),
    [filtered, title, color, granularity],
  );

  const options = useMemo(
    () => lineChartOptions(valueLabel, undefined, { denseLabels: granularity === "month" }),
    [valueLabel, granularity],
  );

  const hasData = granularity === "year" ? yearSorted.length > 0 : monthSorted.length > 0;
  if (!hasData) return null;

  const defaultSubtitle =
    granularity === "year"
      ? `Evolución por ${granularityLabel("year")} · ${valueLabel}`
      : `Evolución por ${granularityLabel("month")} (fecha de concesión) · ${valueLabel}`;

  return (
    <ChartCard
      title={title}
      subtitle={subtitle ?? defaultSubtitle}
      height={granularity === "month" ? 300 : 280}
      controls={
        <YearRangeControls years={years} from={from} to={to} onFromChange={setFrom} onToChange={setTo} />
      }
    >
      {filtered.length === 0 ? (
        <p className="flex h-full items-center justify-center text-sm text-slate-500">
          Sin datos en el rango seleccionado.
        </p>
      ) : (
        <Line data={chartData} options={options} />
      )}
    </ChartCard>
  );
}
