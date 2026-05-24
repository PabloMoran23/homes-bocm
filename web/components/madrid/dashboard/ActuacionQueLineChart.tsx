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
import { multiLineChartOptions } from "@/lib/dashboard-chart-theme";
import {
  ACTUACION_QUE_LEYENDA,
  getActuacionQueMapStyle,
} from "@/lib/actuacion-que-config";
import type { ActuacionQueCodigo } from "@/lib/actuacion-edificio";
import type {
  LicenciasTimeGranularity,
  MadridDashboardMapaMonth,
  MadridDashboardMapaYear,
} from "@/lib/types";

registerDashboardCharts();

function collectSeriesIds(
  rows: { tipos: { id: string; count: number }[] }[],
): ActuacionQueCodigo[] {
  const seen = new Set<string>();
  const ordered: ActuacionQueCodigo[] = [];
  for (const id of ACTUACION_QUE_LEYENDA) {
    if (rows.some((row) => row.tipos.some((t) => t.id === id && t.count > 0))) {
      ordered.push(id);
      seen.add(id);
    }
  }
  for (const row of rows) {
    for (const t of row.tipos) {
      if (t.count > 0 && !seen.has(t.id) && ACTUACION_QUE_LEYENDA.includes(t.id as ActuacionQueCodigo)) {
        ordered.push(t.id as ActuacionQueCodigo);
        seen.add(t.id);
      }
    }
  }
  return ordered;
}

export function ActuacionQueLineChart({
  title,
  seriesByYear,
  seriesByMonth,
  granularity = "year",
}: {
  title: string;
  seriesByYear: MadridDashboardMapaYear[];
  seriesByMonth?: MadridDashboardMapaMonth[];
  granularity?: LicenciasTimeGranularity;
}) {
  const yearSorted = useMemo(
    () => [...seriesByYear].sort((a, b) => a.year - b.year),
    [seriesByYear],
  );
  const monthSorted = useMemo(
    () => [...(seriesByMonth ?? [])].sort((a, b) => a.month.localeCompare(b.month)),
    [seriesByMonth],
  );

  const activeRows = granularity === "year" ? yearSorted : monthSorted;
  const seriesIds = useMemo(() => collectSeriesIds(activeRows), [activeRows]);

  const years = useMemo(() => {
    if (granularity === "year") return yearSorted.map((s) => s.year);
    return yearsFromMonths(monthSorted.map((m) => m.month));
  }, [granularity, yearSorted, monthSorted]);

  const minY = years[0] ?? 2015;
  const maxY = years[years.length - 1] ?? new Date().getFullYear();
  const [from, setFrom] = useState(minY);
  const [to, setTo] = useState(maxY);

  const { labels, filteredRows } = useMemo(() => {
    if (granularity === "year") {
      const rows = yearSorted.filter((s) => s.year >= from && s.year <= to);
      return { labels: rows.map((r) => String(r.year)), filteredRows: rows };
    }
    const rows = monthSorted.filter((m) => monthInYearRange(m.month, from, to));
    return {
      labels: rows.map((r) => formatMonthLabel(r.month)),
      filteredRows: rows,
    };
  }, [granularity, yearSorted, monthSorted, from, to]);

  const chartData = useMemo(() => {
    const datasets = seriesIds.map((id) => {
      const style = getActuacionQueMapStyle(id);
      const color = style.bg;
      return {
        label: style.label,
        data: filteredRows.map(
          (row) => row.tipos.find((t) => t.id === id)?.count ?? 0,
        ),
        borderColor: color,
        backgroundColor: color,
        tension: 0.3,
        pointRadius: granularity === "month" ? 0 : 3,
        pointHoverRadius: 5,
        pointBackgroundColor: "#fff",
        pointBorderColor: color,
        pointBorderWidth: 2,
        borderWidth: 2,
        fill: false,
      };
    });
    return { labels, datasets };
  }, [filteredRows, seriesIds, labels, granularity]);

  const options = useMemo(
    () => multiLineChartOptions("licencias", { denseLabels: granularity === "month" }),
    [granularity],
  );

  const hasData =
    granularity === "year"
      ? yearSorted.length > 0
      : (seriesByMonth?.length ?? 0) > 0;

  if (!hasData || !seriesIds.length) return null;

  return (
    <ChartCard
      title={title}
      subtitle={`Qué se va a hacer (normalizado) · ${granularityLabel(granularity)} · pulsa la leyenda para ocultar una serie`}
      height={granularity === "month" ? 400 : 380}
      className="lg:col-span-2"
      controls={
        <YearRangeControls years={years} from={from} to={to} onFromChange={setFrom} onToChange={setTo} />
      }
    >
      <Line data={chartData} options={options} />
    </ChartCard>
  );
}
