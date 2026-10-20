export function formatCount(value: number): string {
  return Math.round(value).toLocaleString("es-ES");
}

export function formatSeconds(value: number): string {
  const seconds = Math.max(0, Math.round(value));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
}

export function formatPercent(value: number, digits = 0): string {
  return `${(value * 100).toLocaleString("es-ES", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })}%`;
}

export type DeltaMode = "count" | "points";

export type DeltaModel = {
  text: string;
  direction: "up" | "down" | "flat" | "none";
};

export function describeDelta(current: number, previous: number, mode: DeltaMode): DeltaModel {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return { text: "sin comparación", direction: "none" };
  if (previous === 0 && current === 0) return { text: "sin cambio", direction: "flat" };
  if (previous === 0) return { text: "sin base anterior", direction: "none" };
  const diff = current - previous;
  if (diff === 0) return { text: "igual que el periodo anterior", direction: "flat" };
  const direction = diff > 0 ? "up" : "down";
  if (mode === "points") {
    const points = diff * 100;
    const text = `${points > 0 ? "+" : ""}${points.toLocaleString("es-ES", { maximumFractionDigits: 1, minimumFractionDigits: 1 })} pp`;
    return { text, direction };
  }
  const pct = (diff / Math.abs(previous)) * 100;
  const text = `${pct > 0 ? "+" : ""}${Math.round(pct).toLocaleString("es-ES")}%`;
  return { text, direction };
}
