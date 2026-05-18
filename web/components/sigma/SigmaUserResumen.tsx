"use client";

import { useState } from "react";
import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import { formatSigmaArcgisMs, hasValue } from "@/lib/project-display";
import {
  sigmaCatalogSourceUserLabel,
  sigmaFaseContext,
  sigmaFaseLabel,
  sigmaInfoPublicaFromArcgis,
  sigmaInfoPublicaFromYmd,
  sigmaLayerKindUserLabel,
  sigmaTipoActuacion,
} from "@/lib/sigma-user-labels";
import type { SigmaVisorFicha, SigmaVisorTramite } from "@/lib/types";

export type SigmaResumenFields = {
  expedienteGrupo: string;
  denominacion?: string | null;
  fase?: string | null;
  figEtiq?: string | null;
  tfigAbrev?: string | null;
  organo?: string | null;
  aprobacionMs?: unknown;
  infopubIniMs?: unknown;
  infopubFinMs?: unknown;
  infopubIniYmd?: string | null;
  infopubFinYmd?: string | null;
  source?: string | null;
  layerKind?: string | null;
};

function ResumenCell({
  label,
  value,
  mono,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  if (!hasValue(value)) return null;
  return (
    <div className="rounded-lg bg-slate-50/80 px-3 py-2.5">
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`mt-1 text-sm text-slate-900 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

export function SigmaUserResumen({
  fields,
  visorFicha,
  tramitacion = [],
  onVerTramitacion,
  compact,
}: {
  fields: SigmaResumenFields;
  visorFicha?: SigmaVisorFicha | null;
  tramitacion?: SigmaVisorTramite[];
  onVerTramitacion?: () => void;
  /** Vista densa: sin bloque de fase duplicado, menos márgenes. */
  compact?: boolean;
}) {
  const [techOpen, setTechOpen] = useState(false);

  const tipo = sigmaTipoActuacion(fields.figEtiq, fields.tfigAbrev);
  const fase = sigmaFaseLabel(fields.fase);
  const faseCtx = sigmaFaseContext(fields.fase);
  const ipPeriod =
    sigmaInfoPublicaFromArcgis(fields.infopubIniMs, fields.infopubFinMs) ??
    sigmaInfoPublicaFromYmd(fields.infopubIniYmd, fields.infopubFinYmd);
  const aprobacion = formatSigmaArcgisMs(fields.aprobacionMs);
  const origenUser = sigmaCatalogSourceUserLabel(fields.source);
  const capaUser = sigmaLayerKindUserLabel(fields.layerKind);

  const tramPreview = tramitacion.length > 3 ? tramitacion.slice(-3) : tramitacion;

  const techRows: { label: string; value: string }[] = [];
  if (hasValue(fields.expedienteGrupo)) {
    techRows.push({ label: "Referencia municipal", value: fields.expedienteGrupo });
  }
  if (origenUser) techRows.push({ label: "Registro", value: origenUser });
  if (capaUser) techRows.push({ label: "Tipo en mapa", value: capaUser });

  return (
    <div className={compact ? "space-y-4" : "space-y-6"}>
      {ipPeriod ? (
        <div
          className={`rounded-xl border px-4 py-3 ${
            ipPeriod.isOpen
              ? "border-violet-200 bg-violet-50/80"
              : "border-slate-200 bg-slate-50/80"
          }`}
        >
          <p className="text-sm font-semibold text-slate-900">{ipPeriod.short}</p>
          {ipPeriod.range ? (
            <p className="mt-1 text-sm text-slate-600">{ipPeriod.range}</p>
          ) : null}
          <p className="mt-2 text-xs leading-relaxed text-slate-600">
            Durante este periodo puedes revisar la documentación y presentar alegaciones ante el
            ayuntamiento.
          </p>
        </div>
      ) : null}

      {fase && !compact ? (
        <div className="rounded-xl border border-sky-100 bg-sky-50/60 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-sky-800">Estado actual</p>
          <p className="mt-1 text-base font-semibold text-sky-950">{fase}</p>
          {faseCtx ? <p className="mt-2 text-sm leading-relaxed text-sky-900/90">{faseCtx}</p> : null}
        </div>
      ) : null}

      <dl className={`grid gap-3 sm:grid-cols-2 ${compact ? "gap-2" : "gap-4"}`}>
        <ResumenCell label="Tipo de actuación" value={visorFicha?.figuraTipo ?? tipo} />
        <ResumenCell label="Órgano que tramita" value={fields.organo} />
        <ResumenCell label="Fecha de aprobación" value={aprobacion ?? undefined} />
        <ResumenCell label="Promotor" value={visorFicha?.promotor} />
        <ResumenCell label="Distrito" value={visorFicha?.distrito} />
        <ResumenCell label="Iniciativa" value={visorFicha?.iniciativa} />
        <ResumenCell
          label="Superficie ámbito"
          value={
            visorFicha?.superficieAmbitoM2 != null && visorFicha.superficieAmbitoM2 > 0
              ? `${visorFicha.superficieAmbitoM2.toLocaleString("es-ES")} m²`
              : visorFicha?.superficieAmbitoTexto
          }
        />
        <ResumenCell label="Tipo planeamiento" value={visorFicha?.tipoPlaneamiento} />
        {hasValue(fields.denominacion) && fields.denominacion !== tipo ? (
          <ResumenCell label="Denominación oficial" value={fields.denominacion} />
        ) : null}
      </dl>

      {tramPreview.length > 0 ? (
        <div>
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Últimos hitos</h3>
            {onVerTramitacion && tramitacion.length > tramPreview.length ? (
              <button
                type="button"
                onClick={onVerTramitacion}
                className="text-xs font-medium text-[var(--portal-accent)] hover:underline"
              >
                Ver toda la cronología ({tramitacion.length})
              </button>
            ) : onVerTramitacion && tramitacion.length > 0 ? (
              <button
                type="button"
                onClick={onVerTramitacion}
                className="text-xs font-medium text-[var(--portal-accent)] hover:underline"
              >
                Ver cronología completa
              </button>
            ) : null}
          </div>
          <TramitacionTimeline rows={tramPreview} compact />
        </div>
      ) : null}

      {techRows.length > 0 ? (
        <details
          open={techOpen}
          onToggle={(e) => setTechOpen((e.target as HTMLDetailsElement).open)}
          className="rounded-xl border border-slate-200 bg-slate-50/40"
        >
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-slate-600 hover:text-slate-900">
            Detalles técnicos
          </summary>
          <dl className="grid gap-2 border-t border-slate-200 px-4 py-3 sm:grid-cols-2">
            {techRows.map((row) => (
              <div key={row.label} className="text-sm">
                <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  {row.label}
                </dt>
                <dd
                  className={`mt-0.5 text-slate-800 ${
                    row.label === "Referencia municipal" ? "font-mono text-xs" : ""
                  }`}
                >
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}
    </div>
  );
}
