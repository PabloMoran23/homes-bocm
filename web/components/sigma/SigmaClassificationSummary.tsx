"use client";

import {
  sigmaClassificationResumen,
  sigmaConfidenceLabel,
  type SigmaClassification,
  type SigmaClassificationTag,
} from "@/lib/sigma-classification";
import { PORTAL_TAG_TONE_BORDERED } from "@/lib/portal-tones";

function ClassificationTag({ tag }: { tag: SigmaClassificationTag }) {
  return (
    <span
      title={tag.hint}
      className={`inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${PORTAL_TAG_TONE_BORDERED[tag.tone]}`}
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
    <section className="rounded-2xl border border-[var(--portal-paper-deep)] bg-[var(--portal-paper)] px-4 py-4 shadow-sm sm:px-5">
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
