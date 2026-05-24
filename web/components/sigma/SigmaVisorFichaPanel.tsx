"use client";

import { hasValue } from "@/lib/project-display";
import type { SigmaVisorFicha } from "@/lib/types";

function Cell({ label, value }: { label: string; value?: string | null }) {
  if (!hasValue(value)) return null;
  return (
    <div className="rounded-lg border border-slate-100 bg-white/80 px-3 py-2">
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm leading-snug text-slate-800">{value}</dd>
    </div>
  );
}

export function SigmaVisorFichaPanel({
  ficha,
  compact,
  showFullText = true,
  hideResumen = false,
}: {
  ficha: SigmaVisorFicha;
  compact?: boolean;
  /** Muestra descripción, resumen y observaciones (aunque compact). */
  showFullText?: boolean;
  /** Oculta resumenContenido si ya se muestra arriba. */
  hideResumen?: boolean;
}) {
  const sup =
    ficha.superficieAmbitoM2 != null && ficha.superficieAmbitoM2 > 0
      ? `${ficha.superficieAmbitoM2.toLocaleString("es-ES")} m²`
      : ficha.superficieAmbitoTexto;

  const hasGrid =
    hasValue(ficha.promotor) ||
    hasValue(ficha.distrito) ||
    hasValue(ficha.iniciativa) ||
    hasValue(ficha.tipoPlaneamiento) ||
    hasValue(ficha.figuraTipo) ||
    hasValue(sup) ||
    hasValue(ficha.sistemaActuacion) ||
    hasValue(ficha.unidadTramitadora) ||
    hasValue(ficha.ambitoOrdenacion) ||
    hasValue(ficha.archivoPlanos);

  const hasText =
    hasValue(ficha.descripcionAmbito) ||
    (!hideResumen && hasValue(ficha.resumenContenido)) ||
    hasValue(ficha.observaciones) ||
    hasValue(ficha.alegaciones);

  if (!hasGrid && !hasText) return null;

  const textVisible = showFullText && !compact;

  return (
    <section
      className={`rounded-xl border border-teal-200/60 bg-gradient-to-br from-white to-teal-50/30 ${
        compact ? "p-3.5" : "p-4 sm:p-5"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-teal-800">
          Detalles
        </p>
        {hasValue(ficha.figuraCodigo) ? (
          <span className="font-mono text-[10px] text-teal-700/80">{ficha.figuraCodigo}</span>
        ) : null}
      </div>

      {hasGrid ? (
        <dl
          className={`mt-2.5 grid gap-2 ${compact ? "grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}
        >
          <Cell label="Promotor" value={ficha.promotor} />
          <Cell label="Distrito" value={ficha.distrito} />
          <Cell label="Iniciativa" value={ficha.iniciativa} />
          <Cell label="Figura" value={ficha.figuraTipo} />
          <Cell label="Tipo planeamiento" value={ficha.tipoPlaneamiento} />
          <Cell label="Superficie ámbito" value={sup} />
          <Cell label="Sistema de actuación" value={ficha.sistemaActuacion} />
          <Cell label="Unidad tramitadora" value={ficha.unidadTramitadora} />
          <Cell label="Ámbito ordenación" value={ficha.ambitoOrdenacion} />
          <Cell label="Archivo de planos" value={ficha.archivoPlanos} />
        </dl>
      ) : null}

      {hasValue(ficha.descripcionAmbito) ? (
        <p
          className={`mt-3 text-sm leading-relaxed text-slate-700 ${
            textVisible ? "" : "line-clamp-2"
          }`}
        >
          <span className="font-medium text-slate-800">Ámbito: </span>
          {ficha.descripcionAmbito}
        </p>
      ) : null}

      {hasValue(ficha.resumenContenido) && !hideResumen ? (
        <p
          className={`mt-2 text-sm leading-relaxed text-slate-800 ${
            textVisible ? "" : "line-clamp-4"
          }`}
        >
          <span className="font-medium text-slate-900">Objeto del expediente: </span>
          {ficha.resumenContenido}
        </p>
      ) : null}

      {hasValue(ficha.observaciones) ? (
        <p
          className={`mt-2 text-xs leading-relaxed text-slate-600 ${
            textVisible ? "" : "line-clamp-2"
          }`}
        >
          <span className="font-medium">Observaciones: </span>
          {ficha.observaciones}
        </p>
      ) : null}

      {hasValue(ficha.alegaciones) && textVisible ? (
        <p className="mt-2 text-xs leading-relaxed text-slate-500">
          <span className="font-medium">Alegaciones: </span>
          {ficha.alegaciones}
        </p>
      ) : null}
    </section>
  );
}
