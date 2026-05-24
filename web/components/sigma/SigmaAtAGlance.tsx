"use client";

import { normalizeResumenContenido } from "@/lib/normalize-resumen-contenido";
import { buildSigmaQueImplica, type SigmaPresentationInput } from "@/lib/sigma-presentation";
import { formatM2, type SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import { sigmaFaseShortLabel } from "@/lib/sigma-user-labels";
import type { SigmaVisorFicha } from "@/lib/types";

function FactPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200/80 bg-white px-3 py-2 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}

export function SigmaAtAGlance({
  presentation,
  resumenContenido,
  visorFicha,
  metric,
  lastTramDate,
}: {
  presentation: SigmaPresentationInput;
  resumenContenido?: string | null;
  visorFicha?: SigmaVisorFicha | null;
  metric?: SigmaExpedienteMetric | null;
  lastTramDate?: string | null;
}) {
  const planResumen =
    normalizeResumenContenido(resumenContenido) ??
    normalizeResumenContenido(visorFicha?.resumenContenido);

  const fallback = !planResumen ? buildSigmaQueImplica(presentation) : null;
  const body = planResumen ?? fallback?.body;

  const fase = sigmaFaseShortLabel(presentation.fase);
  const viviendas =
    metric?.num_viviendas_max != null && metric.num_viviendas_max > 0
      ? `Hasta ${metric.num_viviendas_max.toLocaleString("es-ES")} viviendas`
      : null;
  const superficie =
    formatM2(metric?.sup_total_m2) ??
    (visorFicha?.superficieAmbitoM2 != null && visorFicha.superficieAmbitoM2 > 0
      ? formatM2(visorFicha.superficieAmbitoM2)
      : visorFicha?.superficieAmbitoTexto ?? null);

  const facts = [
    fase ? { label: "Estado", value: fase } : null,
    viviendas ? { label: "Viviendas", value: viviendas } : null,
    !viviendas && superficie ? { label: "Ámbito", value: superficie } : null,
    lastTramDate ? { label: "Último movimiento", value: lastTramDate } : null,
  ].filter(Boolean) as { label: string; value: string }[];

  if (!body && !facts.length) return null;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <h2 className="text-sm font-semibold text-slate-900">Qué está pasando</h2>
      {body ? (
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-700">{body}</p>
      ) : null}
      {facts.length ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {facts.map((fact) => (
            <FactPill key={fact.label} label={fact.label} value={fact.value} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
