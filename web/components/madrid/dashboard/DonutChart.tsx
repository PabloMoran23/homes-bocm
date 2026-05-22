"use client";

import { useMemo } from "react";
import { Doughnut } from "react-chartjs-2";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { registerDashboardCharts } from "@/components/madrid/dashboard/register-charts";
import {
  baseAnimation,
  CHART_COLORS,
  DONUT_PALETTE,
  fmtChart,
} from "@/lib/dashboard-chart-theme";
import type { MadridDashboardCount } from "@/lib/types";
import type { ChartOptions } from "chart.js";

registerDashboardCharts();

function formatSliceName(name: string) {
  return name
    .split(/\s+/)
    .map((w) => (w.length <= 3 ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

function sliceWithOthers(items: MadridDashboardCount[], maxItems: number): MadridDashboardCount[] {
  const head = items.slice(0, maxItems);
  const tail = items.slice(maxItems);
  if (!tail.length) return head;
  const otros = tail.reduce((s, x) => s + x.count, 0);
  return [...head, { name: "Otros", count: otros }];
}

export function DonutChart({
  title,
  items,
  maxItems = 8,
  valueLabel = "registros",
}: {
  title: string;
  items: MadridDashboardCount[];
  maxItems?: number;
  valueLabel?: string;
}) {
  const slices = useMemo(() => sliceWithOthers(items, maxItems), [items, maxItems]);
  const total = useMemo(() => slices.reduce((s, x) => s + x.count, 0), [slices]);

  const chartData = useMemo(
    () => ({
      labels: slices.map((s) => formatSliceName(s.name)),
      datasets: [
        {
          data: slices.map((s) => s.count),
          backgroundColor: slices.map((_, i) => DONUT_PALETTE[i % DONUT_PALETTE.length]),
          borderColor: "#ffffff",
          borderWidth: 2,
          hoverBorderWidth: 2,
          hoverOffset: 6,
        },
      ],
    }),
    [slices],
  );

  const options = useMemo<ChartOptions<"doughnut">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: baseAnimation(),
      cutout: "58%",
      plugins: {
        legend: {
          position: "right",
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: true,
            pointStyle: "circle",
            padding: 10,
            color: "#475569",
            font: { size: 11 },
          },
        },
        tooltip: {
          backgroundColor: CHART_COLORS.tooltipBg,
          borderColor: CHART_COLORS.tooltipBorder,
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed ?? 0;
              const pct = total > 0 ? ((v / total) * 100).toFixed(1) : "0";
              return ` ${fmtChart(v)} ${valueLabel} (${pct} %)`;
            },
          },
        },
      },
    }),
    [total, valueLabel],
  );

  if (!slices.length) {
    return (
      <ChartCard title={title} height={280}>
        <p className="flex h-full items-center justify-center text-sm text-slate-500">Sin datos.</p>
      </ChartCard>
    );
  }

  return (
    <ChartCard
      title={title}
      subtitle={`${fmtChart(total)} ${valueLabel} · top ${Math.min(maxItems, items.length)}${items.length > maxItems ? " + otros" : ""}`}
      height={300}
    >
      <Doughnut data={chartData} options={options} />
    </ChartCard>
  );
}
