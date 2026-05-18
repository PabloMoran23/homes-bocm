"use client";

import { buildSigmaQueImplica, type SigmaPresentationInput } from "@/lib/sigma-presentation";

export function SigmaQueImplicaBlock({
  presentation,
  compact,
}: {
  presentation: SigmaPresentationInput;
  compact?: boolean;
}) {
  const q = buildSigmaQueImplica(presentation);

  const confLabel =
    q.confidence === "alta"
      ? "Alta"
      : q.confidence === "media"
        ? "Media"
        : "Orientativo";

  return (
    <div
      className={`rounded-xl border border-amber-200/80 bg-gradient-to-br from-amber-50/90 to-orange-50/40 ${
        compact ? "px-3.5 py-3" : "px-4 py-3.5"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-900">
          De qué va el proyecto
        </p>
        <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium text-amber-800 ring-1 ring-amber-200/80">
          Confianza {confLabel.toLowerCase()}
        </span>
      </div>
      <p className={`mt-1.5 font-semibold text-amber-950 ${compact ? "text-sm" : "text-base"}`}>
        {q.title}
      </p>
      <p className={`mt-2 leading-relaxed text-amber-950/90 ${compact ? "text-xs" : "text-sm"}`}>
        {q.body}
      </p>
      {q.ejemplos?.length ? (
        <p className={`mt-2 text-amber-900/75 ${compact ? "text-[11px]" : "text-xs"}`}>
          <span className="font-medium">Ejemplos habituales en este tipo:</span>{" "}
          {q.ejemplos.join(" · ")}
          <span className="text-amber-800/60"> (no confirma que apliquen aquí)</span>
        </p>
      ) : null}
      <p className={`mt-2 text-amber-800/65 ${compact ? "text-[10px]" : "text-[11px]"}`}>
        Fuente: {q.source}
      </p>
    </div>
  );
}
