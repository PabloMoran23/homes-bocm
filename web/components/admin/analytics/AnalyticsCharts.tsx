"use client";

import { useMemo } from "react";
import { Bar, Doughnut, Line } from "react-chartjs-2";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { registerDashboardCharts } from "@/components/madrid/dashboard/register-charts";
import {
  CHART_COLORS,
  DONUT_PALETTE,
  PORTAL_TEAL,
  PORTAL_TEAL_LIGHT,
  baseAnimation,
  baseLegendOptions,
  baseScaleOptions,
  fmtChart,
} from "@/lib/dashboard-chart-theme";
import type { ChartModel } from "@/lib/analytics-dashboard";

registerDashboardCharts();

const HUMAN = "#1f4f53";
const BOT = "#c07f6c";
const ADMIN = "#d4923a";

export function AnalyticsCharts({ charts }: { charts: ChartModel }) {
  const hasSessions = charts.series.some((point) => point.human + point.bot + point.admin > 0);
  const hasViews = charts.series.some((point) => point.pageviews > 0);
  const mixTotal = charts.mix.human + charts.mix.bot + charts.mix.admin;
  const grain = charts.granularity === "hour" ? "Por hora, hora de Madrid." : "Por día, hora de Madrid.";

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartCard title="Sesiones" subtitle={`${grain} Personas, bots y administradores.`} height={300} className="lg:col-span-2">
        {hasSessions ? <SessionTrend series={charts.series} /> : <EmptyChart label="No hay sesiones en este periodo." />}
      </ChartCard>
      <ChartCard title="Páginas vistas" subtitle={grain} height={260}>
        {hasViews ? <PageviewTrend series={charts.series} /> : <EmptyChart label="No hay páginas vistas en este periodo." />}
      </ChartCard>
      <ChartCard title="Composición del tráfico" subtitle="Ignora el filtro de tipo. Respeta fechas, origen y sección." height={260}>
        {mixTotal ? <MixDonut mix={charts.mix} /> : <EmptyChart label="Sin sesiones para componer el tráfico." />}
      </ChartCard>
      <ChartCard title="Tiempo activo" subtitle="Sesiones del filtro actual." height={240}>
        <Distribution series={charts.active} color={HUMAN} />
      </ChartCard>
      <ChartCard title="Profundidad de scroll" subtitle="Páginas con medición. El scroll no demuestra lectura." height={240}>
        <Distribution series={charts.scroll} color={DONUT_PALETTE[1]} />
      </ChartCard>
    </div>
  );
}

function SessionTrend({ series }: { series: ChartModel["series"] }) {
  const data = useMemo(
    () => ({
      labels: series.map((point) => point.label),
      datasets: [
        line(series.map((point) => point.human), "Personas", HUMAN),
        line(series.map((point) => point.bot), "Bots", BOT),
        line(series.map((point) => point.admin), "Admin", ADMIN),
      ],
    }),
    [series],
  );
  const options = useMemo(() => trendOptions("sesiones"), []);
  const summary = series
    .map((point) => `${point.label}: ${point.human} personas, ${point.bot} bots, ${point.admin} admin`)
    .join(". ");
  return (
    <div className="h-full" role="img" aria-label={`Sesiones. ${summary}`}>
      <Line data={data} options={options} />
    </div>
  );
}

function PageviewTrend({ series }: { series: ChartModel["series"] }) {
  const data = useMemo(
    () => ({
      labels: series.map((point) => point.label),
      datasets: [
        {
          label: "Páginas vistas",
          data: series.map((point) => point.pageviews),
          borderColor: PORTAL_TEAL,
          backgroundColor: PORTAL_TEAL_LIGHT,
          fill: true,
          tension: 0.25,
          pointRadius: 2,
          borderWidth: 2,
        },
      ],
    }),
    [series],
  );
  return (
    <div className="h-full" role="img" aria-label="Páginas vistas en el periodo">
      <Line data={data} options={trendOptions("vistas")} />
    </div>
  );
}

function MixDonut({ mix }: { mix: ChartModel["mix"] }) {
  const data = useMemo(
    () => ({
      labels: ["Personas", "Bots", "Admin"],
      datasets: [
        {
          data: [mix.human, mix.bot, mix.admin],
          backgroundColor: [HUMAN, BOT, ADMIN],
          borderWidth: 0,
          hoverOffset: 4,
        },
      ],
    }),
    [mix],
  );
  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: baseAnimation(),
      plugins: {
        legend: baseLegendOptions("bottom"),
        tooltip: {
          backgroundColor: CHART_COLORS.tooltipBg,
          callbacks: {
            label: (item: { label?: string; parsed?: number }) => ` ${item.label}: ${fmtChart(item.parsed ?? 0)} sesiones`,
          },
        },
      },
    }),
    [],
  );
  return (
    <div className="h-full" role="img" aria-label={`Composición: ${mix.human} personas, ${mix.bot} bots, ${mix.admin} admin`}>
      <Doughnut data={data} options={options} />
    </div>
  );
}

function Distribution({ series, color }: { series: { label: string; value: number }[]; color: string }) {
  const data = useMemo(
    () => ({
      labels: series.map((item) => item.label),
      datasets: [
        {
          data: series.map((item) => item.value),
          backgroundColor: color,
          borderRadius: 6,
          maxBarThickness: 28,
        },
      ],
    }),
    [series, color],
  );
  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: baseAnimation(),
      plugins: { legend: { display: false } },
      scales: baseScaleOptions(),
    }),
    [],
  );
  return (
    <div className="h-full">
      <Bar data={data} options={options} />
    </div>
  );
}

function line(data: number[], label: string, color: string) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color,
    tension: 0.25,
    pointRadius: 2,
    borderWidth: 2,
  };
}

function trendOptions(unit: string) {
  const scales = baseScaleOptions();
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index" as const, intersect: false },
    animation: baseAnimation(),
    plugins: {
      legend: baseLegendOptions("bottom"),
      tooltip: {
        backgroundColor: CHART_COLORS.tooltipBg,
        borderColor: CHART_COLORS.tooltipBorder,
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
        callbacks: {
          label: (item: { dataset: { label?: string }; parsed: { y: number | null } }) =>
            ` ${item.dataset.label}: ${fmtChart(item.parsed.y ?? 0)} ${unit}`,
        },
      },
    },
    scales: {
      ...scales,
      x: {
        ...scales.x,
        ticks: { ...scales.x.ticks, maxTicksLimit: 8, maxRotation: 0 },
      },
    },
  };
}

function EmptyChart({ label }: { label: string }) {
  return <p className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-500">{label}</p>;
}
