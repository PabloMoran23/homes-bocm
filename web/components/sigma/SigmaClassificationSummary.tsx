"use client";

import {
  sigmaClassificationResumen,
  sigmaClassificationTone,
  sigmaConfidenceLabel,
  type SigmaClassification,
  type SigmaClassificationTag,
} from "@/lib/sigma-classification";

const TAG_CLASS: Record<ReturnType<typeof sigmaClassificationTone>, string> = {
  teal: "border-teal-200 bg-teal-50 text-teal-950 ring-teal-100",
  violet: "border-violet-200 bg-violet-50 text-violet-950 ring-violet-100",
  amber: "border-amber-200 bg-amber-50 text-amber-950 ring-amber-100",
  sky: "border-sky-200 bg-sky-50 text-sky-950 ring-sky-100",
  slate: "border-slate-200 bg-white text-slate-800 ring-slate-100",
};

function ClassificationTag({ tag }: { tag: SigmaClassificationTag }) {
  return (
    <span
      title={tag.hint}
      className={`inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${TAG_CLASS[tag.tone]}`}
    >
      <span className="truncate">{tag.label}</span>
    </span>
  );
}

export function SigmaClassificationSummary({
  value,
  compact = false,
}: {
  value?: SigmaClassification | null;
  /** Encima del mapa: sin caja pesada, solo etiquetas. */
  compact?: boolean;
}) {
  const resumen = sigmaClassificationResumen(value);
  if (!resumen) return null;

  const confianza = sigmaConfidenceLabel(value?.confianza);

  if (compact) {
    return (
      <div className="space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Proyecto
          </p>
          {confianza ? (
            <span className="text-[10px] font-medium text-slate-400" title={confianza}>
              {confianza}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {resumen.tags.map((tag) => (
            <ClassificationTag key={tag.id} tag={tag} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white px-4 py-4 shadow-sm sm:px-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-900">De qué va este proyecto</p>
        {confianza ? (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            {confianza}
          </span>
        ) : null}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-700">{resumen.headline}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {resumen.tags.map((tag) => (
          <ClassificationTag key={tag.id} tag={tag} />
        ))}
      </div>
      <ul className="mt-3 space-y-1.5 border-t border-slate-100 pt-3">
        {resumen.tags.map((tag) => (
          <li key={`${tag.id}-hint`} className="text-xs leading-relaxed text-slate-500">
            <span className="font-semibold text-slate-700">{tag.label}:</span> {tag.hint}
          </li>
        ))}
      </ul>
    </section>
  );
}
