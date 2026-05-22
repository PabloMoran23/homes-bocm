"use client";

import { useMemo } from "react";
import { Bar } from "react-chartjs-2";
import { ChartCard } from "@/components/madrid/dashboard/ChartCard";
import { registerDashboardCharts } from "@/components/madrid/dashboard/register-charts";
import { horizontalBarOptions } from "@/lib/dashboard-chart-theme";
import type { MadridDashboardCount } from "@/lib/types";

registerDashboardCharts();

function formatName(name: string) {
  return name
    .split(/\s+/)
    .map((w) => (w.length <= 3 ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

function truncateLabel(name: string, max = 26) {
  const formatted = formatName(name);
  return formatted.length > max ? `${formatted.slice(0, max - 1)}…` : formatted;
}

export function BarRanking({
  title,
  items,
  maxItems = 12,
  valueLabel = "expedientes",
}: {
  title: string;
  items: MadridDashboardCount[];
  maxItems?: number;
  valueLabel?: string;
}) {
  const slice = items.slice(0, maxItems);

  const chartData = useMemo(() => {
    const reversed = [...slice].reverse();
    return {
      labels: reversed.map((r) => truncateLabel(r.name)),
      datasets: [
        {
          data: reversed.map((r) => r.count),
          backgroundColor: reversed.map((_, i) => {
            const t = i / Math.max(1, reversed.length - 1);
            const alpha = 0.45 + (1 - t) * 0.55;
            return `rgba(15, 118, 110, ${alpha})`;
          }),
          borderRadius: 6,
          borderSkipped: false,
          barThickness: 14,
        },
      ],
    };
  }, [slice]);

  const options = useMemo(
    () => horizontalBarOptions(valueLabel, maxItems),
    [valueLabel, maxItems],
  );

  const height = Math.max(200, slice.length * 36 + 48);

  if (!slice.length) {
    return (
      <ChartCard title={title} height={160}>
        <p className="flex h-full items-center justify-center text-sm text-slate-500">Sin datos.</p>
      </ChartCard>
    );
  }

  return (
    <ChartCard
      title={title}
      subtitle={`Top ${slice.length} · ${valueLabel}`}
      height={height}
    >
      <Bar data={chartData} options={options} />
    </ChartCard>
  );
}
