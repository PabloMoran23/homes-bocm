"use client";

import {
  formatM2,
  metricCoverageBadge,
  type SigmaExpedienteMetric,
  viviendaNuevaLabel,
} from "@/lib/sigma-metrics";

export function ViviendaBadge({ code }: { code: string | null | undefined }) {
  const label = viviendaNuevaLabel(code);
  const tone =
    code === "si" || code === "probable_si"
      ? "bg-teal-50 text-teal-900 ring-teal-200"
      : code === "no" || code === "stock_existente_o_rehabilitacion"
        ? "bg-slate-100 text-slate-700 ring-slate-200"
        : "bg-amber-50 text-amber-900 ring-amber-200";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${tone}`}>
      {label}
    </span>
  );
}

export function KpiTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-xl px-4 py-3 ring-1 ${
        accent
          ? "bg-gradient-to-br from-teal-50 to-white ring-teal-200/80"
          : "bg-white/95 ring-slate-200/90"
      }`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">{value}</p>
      {sub ? <p className="mt-0.5 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}

export function SigmaMetricsPanel({
  metric,
  compact,
}: {
  metric: SigmaExpedienteMetric | null;
  compact?: boolean;
}) {
  const cov = metricCoverageBadge(Boolean(metric));

  return (
    <div className="space-y-3">
      {!compact ? (
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${
              cov.tone === "teal"
                ? "bg-teal-50 text-teal-900 ring-teal-200"
                : "bg-slate-100 text-slate-600 ring-slate-200"
            }`}
          >
            {cov.label}
          </span>
          {metric?.genera_vivienda_nueva ? (
            <ViviendaBadge code={metric.genera_vivienda_nueva} />
          ) : null}
        </div>
      ) : metric?.genera_vivienda_nueva ? (
        <ViviendaBadge code={metric.genera_vivienda_nueva} />
      ) : null}

      {metric ? (
        <div className={`grid gap-3 ${compact ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-2"}`}>
          {metric.num_viviendas_max != null ? (
            <KpiTile
              label="Viviendas"
              value={`Hasta ${metric.num_viviendas_max.toLocaleString("es-ES")}`}
              sub="Según documentación analizada"
              accent
            />
          ) : null}
          {formatM2(metric.sup_total_m2) ? (
            <KpiTile label="Superficie ámbito" value={formatM2(metric.sup_total_m2)!} />
          ) : null}
          {formatM2(metric.sup_edificable_m2) && !compact ? (
            <KpiTile label="Superficie edificable aprox." value={formatM2(metric.sup_edificable_m2)!} />
          ) : null}
          {metric.tipo_vivienda && !compact ? (
            <KpiTile label="Tipo vivienda" value={metric.tipo_vivienda} />
          ) : null}
        </div>
      ) : compact ? null : (
        <p className="text-sm leading-relaxed text-slate-600">
          Todavía no hemos extraído cifras de viviendas o superficie de los documentos de este
          expediente. Puedes ver el estado y la tramitación en las otras pestañas.
        </p>
      )}

      {metric?.hechos?.length ? (
        <details className="rounded-xl border border-slate-200 bg-slate-50/50">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-slate-600 hover:text-slate-900">
            Ver fuentes y cifras extraídas
          </summary>
          <ul className="space-y-2 border-t border-slate-200 px-4 py-3">
            {metric.hechos.map((h, i) => (
              <li key={i} className="text-xs text-slate-700">
                <span className="font-medium text-slate-900">{h.metric}</span>
                {": "}
                <span className="tabular-nums">{String(h.value)}</span>
                {h.confianza ? (
                  <span className="text-slate-400"> · {h.confianza}</span>
                ) : null}
                {h.pdf_name ? (
                  <span className="mt-0.5 block truncate text-slate-500" title={h.pdf_name}>
                    {h.pdf_name}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
          <p className="border-t border-slate-200 px-4 py-3 text-[11px] text-slate-400">
            No es resolución vinculante; consulta los documentos oficiales.
          </p>
        </details>
      ) : null}
    </div>
  );
}
