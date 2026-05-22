import type { ChartOptions, TooltipItem } from "chart.js";

export const PORTAL_TEAL = "#0f766e";
export const PORTAL_TEAL_LIGHT = "rgba(15, 118, 110, 0.12)";

export const DONUT_PALETTE = [
  "#0f766e",
  "#14b8a6",
  "#0ea5e9",
  "#6366f1",
  "#8b5cf6",
  "#d946ef",
  "#f43f5e",
  "#f97316",
  "#eab308",
  "#84cc16",
  "#64748b",
  "#94a3b8",
];

export const CHART_COLORS = {
  grid: "rgba(148, 163, 184, 0.25)",
  tick: "#64748b",
  tickMuted: "#94a3b8",
  tooltipBg: "rgba(15, 23, 42, 0.92)",
  tooltipBorder: "rgba(51, 65, 85, 0.5)",
};

export function fmtChart(n: number): string {
  return n.toLocaleString("es-ES");
}

export function tooltipValue(
  items: TooltipItem<"line" | "bar">[],
  label = "registros",
): string {
  const item = items[0];
  if (!item) return "";
  const v =
    (typeof item.parsed.y === "number" ? item.parsed.y : item.parsed.x) ?? 0;
  return `${fmtChart(v)} ${label}`;
}

export function baseAnimation() {
  return {
    duration: 800,
    easing: "easeOutQuart" as const,
  };
}

export function baseLegendOptions(position: "top" | "bottom" = "bottom") {
  return {
    position,
    align: "start" as const,
    labels: {
      boxWidth: 10,
      boxHeight: 10,
      usePointStyle: true,
      pointStyle: "circle" as const,
      padding: 14,
      color: "#475569",
      font: { family: "var(--font-geist-sans), system-ui, sans-serif", size: 11 },
    },
  };
}

export function baseScaleOptions() {
  return {
    x: {
      grid: { display: false },
      border: { display: false },
      ticks: {
        color: CHART_COLORS.tick,
        font: { size: 11 },
        maxRotation: 0,
      },
    },
    y: {
      beginAtZero: true,
      grid: { color: CHART_COLORS.grid },
      border: { display: false },
      ticks: {
        color: CHART_COLORS.tickMuted,
        font: { size: 11 },
        callback: (value: string | number) => {
          const n = Number(value);
          if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
          if (n >= 10_000) return `${Math.round(n / 1000)}k`;
          if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
          return n;
        },
      },
    },
  };
}

export function lineChartOptions(
  valueLabel: string,
  overrides?: Partial<ChartOptions<"line">>,
  opts?: { denseLabels?: boolean },
): ChartOptions<"line"> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    animation: baseAnimation(),
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: CHART_COLORS.tooltipBg,
        borderColor: CHART_COLORS.tooltipBorder,
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
        titleFont: { size: 12, weight: "bold" },
        bodyFont: { size: 12 },
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed.y ?? 0;
            return ` ${fmtChart(v)} ${valueLabel}`;
          },
        },
      },
    },
    scales: {
      ...baseScaleOptions(),
      x: {
        ...baseScaleOptions().x,
        ticks: {
          ...baseScaleOptions().x?.ticks,
          maxTicksLimit: opts?.denseLabels ? 14 : undefined,
          maxRotation: opts?.denseLabels ? 45 : 0,
          minRotation: opts?.denseLabels ? 0 : 0,
        },
      },
    },
    ...overrides,
  };
}

export function multiLineChartOptions(
  valueLabel: string,
  opts?: { denseLabels?: boolean },
): ChartOptions<"line"> {
  return {
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
        filter: (item) => (item.parsed.y ?? 0) > 0 || item.dataset.hidden !== true,
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed.y ?? 0;
            return ` ${ctx.dataset.label}: ${fmtChart(v)} ${valueLabel}`;
          },
        },
      },
    },
    scales: {
      ...baseScaleOptions(),
      x: {
        ...baseScaleOptions().x,
        ticks: {
          ...baseScaleOptions().x?.ticks,
          maxTicksLimit: opts?.denseLabels ? 14 : undefined,
          maxRotation: opts?.denseLabels ? 45 : 0,
        },
      },
    },
  };
}

export function horizontalBarOptions(
  valueLabel: string,
  maxItems: number,
): ChartOptions<"bar"> {
  return {
    indexAxis: "y" as const,
    responsive: true,
    maintainAspectRatio: false,
    animation: baseAnimation(),
    layout: { padding: { right: 8 } },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: CHART_COLORS.tooltipBg,
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        callbacks: {
          label: (ctx) => ` ${fmtChart(ctx.parsed.x ?? 0)} ${valueLabel}`,
        },
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        grid: { color: CHART_COLORS.grid },
        border: { display: false },
        ticks: {
          color: CHART_COLORS.tickMuted,
          font: { size: 10 },
          callback: (value) => {
            const n = Number(value);
            if (n >= 10_000) return `${Math.round(n / 1000)}k`;
            return n;
          },
        },
      },
      y: {
        grid: { display: false },
        border: { display: false },
        ticks: {
          color: CHART_COLORS.tick,
          font: { size: 10 },
          autoSkip: false,
        },
      },
    },
  };
}
