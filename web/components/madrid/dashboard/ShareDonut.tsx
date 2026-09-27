"use client";

import { useMemo } from "react";
import { Doughnut } from "react-chartjs-2";
import { registerDashboardCharts } from "@/components/madrid/dashboard/register-charts";
import { baseAnimation, DONUT_PALETTE, fmtChart } from "@/lib/dashboard-chart-theme";
import type { PresentacionCount } from "@/lib/madrid-presentacion";

registerDashboardCharts();

export function ShareDonut({
  items,
  centerLabel,
  centerHint,
}: {
  items: PresentacionCount[];
  centerLabel: string;
  centerHint: string;
}) {
  const data = useMemo(
    () => ({
      labels: items.map((item) => item.name),
      datasets: [
        {
          data: items.map((item) => item.count),
          backgroundColor: items.map((_, i) => DONUT_PALETTE[i % DONUT_PALETTE.length]),
          borderColor: "#f7f3eb",
          borderWidth: 3,
          hoverOffset: 4,
        },
      ],
    }),
    [items],
  );

  return (
    <div className="relative h-[220px]">
      <Doughnut
        data={data}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          cutout: "68%",
          animation: baseAnimation(),
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.label}: ${fmtChart(ctx.parsed)}`,
              },
            },
          },
        }}
      />
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <p className="text-2xl font-semibold tabular-nums text-[var(--portal-ink)]">{centerLabel}</p>
        <p className="mt-0.5 max-w-[7rem] text-center text-[10px] leading-tight text-slate-500">
          {centerHint}
        </p>
      </div>
    </div>
  );
}
