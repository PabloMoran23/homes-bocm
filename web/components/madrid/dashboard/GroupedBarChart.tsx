"use client";

import { useMemo } from "react";
import { Bar } from "react-chartjs-2";
import type { ChartOptions } from "chart.js";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { registerDashboardCharts } from "@/components/madrid/dashboard/register-charts";
import {
  baseAnimation,
  baseLegendOptions,
  baseScaleOptions,
  CHART_COLORS,
  DONUT_PALETTE,
  fmtChart,
} from "@/lib/dashboard-chart-theme";

registerDashboardCharts();

export function GroupedBarChart({
  title,
  subtitle,
  categories,
  series,
  stacked = false,
  valueLabel = "licencias",
  height = 300,
}: {
  title: string;
  subtitle?: string;
  categories: string[];
  series: { name: string; data: number[] }[];
  stacked?: boolean;
  valueLabel?: string;
  height?: number;
}) {
  const data = useMemo(
    () => ({
      labels: categories,
      datasets: series.map((item, i) => ({
        label: item.name,
        data: item.data,
        backgroundColor: DONUT_PALETTE[i % DONUT_PALETTE.length],
        borderRadius: stacked ? 0 : 6,
        borderSkipped: false,
        maxBarThickness: 28,
      })),
    }),
    [categories, series, stacked],
  );

  const options = useMemo<ChartOptions<"bar">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
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
            label: (ctx) => ` ${ctx.dataset.label}: ${fmtChart(ctx.parsed.y ?? 0)} ${valueLabel}`,
          },
        },
      },
      scales: {
        x: { ...baseScaleOptions().x, stacked },
        y: { ...baseScaleOptions().y, stacked },
      },
    }),
    [stacked, valueLabel],
  );

  return (
    <ChartCard title={title} subtitle={subtitle} height={height}>
      <Bar data={data} options={options} />
    </ChartCard>
  );
}
