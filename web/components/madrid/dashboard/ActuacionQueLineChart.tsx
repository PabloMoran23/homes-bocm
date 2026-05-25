"use client";

import { useEffect, useMemo, useState } from "react";
import { Line } from "react-chartjs-2";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { registerDashboardCharts } from "@/components/madrid/dashboard/register-charts";
import { YearRangeControls } from "@/components/madrid/dashboard/YearRangeControls";
import {
  formatMonthLabel,
  granularityLabel,
  monthInDetailRange,
  monthOnOrAfter,
  yearsFromMonths,
} from "@/lib/dashboard-time";
import {
  LICENCIAS_DETALLE_MIN_MONTH,
  LICENCIAS_DETALLE_MIN_YEAR,
} from "@/lib/licencias-actuacion-familias";
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
  cutFromOrdenanza = false,
}: {
  title: string;
  seriesByYear: MadridDashboardMapaYear[];
  seriesByMonth?: MadridDashboardMapaMonth[];
  granularity?: LicenciasTimeGranularity;
  /** Excluye datos anteriores a 2023 (etiquetado homogéneo). */
  cutFromOrdenanza?: boolean;
}) {
  const yearSorted = useMemo(
    () => [...seriesByYear].sort((a, b) => a.year - b.year),
    [seriesByYear],
  );
  const monthSorted = useMemo(() => {
    const rows = [...(seriesByMonth ?? [])].sort((a, b) => a.month.localeCompare(b.month));
    if (!cutFromOrdenanza) return rows;
    return rows.filter((m) => monthOnOrAfter(m.month, LICENCIAS_DETALLE_MIN_MONTH));
  }, [seriesByMonth, cutFromOrdenanza]);

  const yearSortedCut = useMemo(() => {
    if (!cutFromOrdenanza) return yearSorted;
    return yearSorted.filter((s) => s.year >= LICENCIAS_DETALLE_MIN_YEAR);
  }, [yearSorted, cutFromOrdenanza]);

  const activeRows = granularity === "year" ? yearSortedCut : monthSorted;
  const seriesIds = useMemo(() => collectSeriesIds(activeRows), [activeRows]);

  const years = useMemo(() => {
    if (granularity === "year") return yearSortedCut.map((s) => s.year);
    return yearsFromMonths(monthSorted.map((m) => m.month));
  }, [granularity, yearSortedCut, monthSorted]);

  const minY = years[0] ?? (cutFromOrdenanza ? LICENCIAS_DETALLE_MIN_YEAR : 2015);
  const maxY = years[years.length - 1] ?? new Date().getFullYear();
  const initialFrom = cutFromOrdenanza
    ? Math.max(minY, LICENCIAS_DETALLE_MIN_YEAR)
    : minY;
  const [from, setFrom] = useState(initialFrom);
  const [to, setTo] = useState(maxY);

  useEffect(() => {
    if (!cutFromOrdenanza) return;
    if (from < LICENCIAS_DETALLE_MIN_YEAR) setFrom(LICENCIAS_DETALLE_MIN_YEAR);
  }, [cutFromOrdenanza, from]);

  const { labels, filteredRows } = useMemo(() => {
    if (granularity === "year") {
      const rows = yearSortedCut.filter((s) => s.year >= from && s.year <= to);
      return { labels: rows.map((r) => String(r.year)), filteredRows: rows };
    }
    const minMonth = cutFromOrdenanza ? LICENCIAS_DETALLE_MIN_MONTH : "0000-01";
    const rows = monthSorted.filter((m) => monthInDetailRange(m.month, from, to, minMonth));
    return {
      labels: rows.map((r) => formatMonthLabel(r.month)),
      filteredRows: rows,
    };
  }, [granularity, yearSortedCut, monthSorted, from, to, cutFromOrdenanza]);

  const detalleDesdeLabel = cutFromOrdenanza
    ? String(LICENCIAS_DETALLE_MIN_YEAR)
    : String(initialFrom);

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
    granularity === "year" ? yearSortedCut.length > 0 : monthSorted.length > 0;

  if (!hasData || !seriesIds.length) return null;

  return (
    <ChartCard
      title={title}
      subtitle={`Desde ${detalleDesdeLabel} · ${granularityLabel(granularity)} · pulsa la leyenda para ocultar una serie`}
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
