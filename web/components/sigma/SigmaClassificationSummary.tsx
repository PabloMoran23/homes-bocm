"use client";

import {
  sigmaClassificationLabel,
  sigmaClassificationTone,
  sigmaConfidenceLabel,
  type SigmaClassification,
} from "@/lib/sigma-classification";

const TONE_CLASS: Record<ReturnType<typeof sigmaClassificationTone>, string> = {
  teal: "border-teal-200 bg-teal-50/70 text-teal-950",
  violet: "border-violet-200 bg-violet-50/70 text-violet-950",
  amber: "border-amber-200 bg-amber-50/70 text-amber-950",
  sky: "border-sky-200 bg-sky-50/70 text-sky-950",
  slate: "border-slate-200 bg-slate-50/70 text-slate-950",
};

export function SigmaClassificationSummary({
  value,
}: {
  value?: SigmaClassification | null;
}) {
  if (!value?.categoriaProyecto) return null;

  const tone = sigmaClassificationTone(value.categoriaProyecto);
  const rows = [
    ["Tipo", value.tipoLegal],
    ["Escala", value.escala],
    ["Contenido", value.contenidoPrincipal],
    ["Fase", value.faseNormalizada],
  ]
    .map(([label, raw]) => ({ label, value: sigmaClassificationLabel(raw) }))
    .filter((row) => row.value);

  if (!rows.length) return null;

  return (
    <section className={`rounded-xl border px-4 py-3 ${TONE_CLASS[tone]}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">
          {sigmaClassificationLabel(value.categoriaProyecto)}
        </p>
        {sigmaConfidenceLabel(value.confianza) ? (
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
            {sigmaConfidenceLabel(value.confianza)}
          </span>
        ) : null}
      </div>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {rows.map((row) => (
          <div key={row.label} className="rounded-lg bg-white/60 px-3 py-2">
            <dt className="text-[10px] font-semibold uppercase tracking-wide opacity-60">
              {row.label}
            </dt>
            <dd className="mt-0.5 text-xs font-medium">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
