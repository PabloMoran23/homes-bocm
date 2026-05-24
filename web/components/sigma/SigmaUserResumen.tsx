"use client";

import { formatSigmaArcgisMs, hasValue } from "@/lib/project-display";
import type { SigmaClassification } from "@/lib/sigma-classification";
import {
  sigmaCatalogSourceUserLabel,
  sigmaInfoPublicaFromArcgis,
  sigmaInfoPublicaFromYmd,
  sigmaLayerKindUserLabel,
  sigmaVisorFieldLabel,
} from "@/lib/sigma-user-labels";
import type { SigmaVisorFicha } from "@/lib/types";

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

export function SigmaInfoPublicaBanner({ fields }: { fields: SigmaResumenFields }) {
  const ipPeriod =
    sigmaInfoPublicaFromArcgis(fields.infopubIniMs, fields.infopubFinMs) ??
    sigmaInfoPublicaFromYmd(fields.infopubIniYmd, fields.infopubFinYmd);

  if (!ipPeriod) return null;

  return (
    <div
      className={`rounded-xl border px-4 py-3 ${
        ipPeriod.isOpen
          ? "border-violet-200 bg-violet-50/80"
          : "border-slate-200 bg-slate-50/80"
      }`}
    >
      <p className="text-sm font-semibold text-slate-900">{ipPeriod.short}</p>
      {ipPeriod.range ? <p className="mt-1 text-sm text-slate-600">{ipPeriod.range}</p> : null}
      {ipPeriod.isOpen ? (
        <p className="mt-2 text-xs leading-relaxed text-slate-600">
          Puedes revisar la documentación y presentar alegaciones ante el ayuntamiento durante este
          periodo.
        </p>
      ) : null}
    </div>
  );
}

export function SigmaTechnicalDetails({
  fields,
  visorFicha,
  clasificacion,
}: {
  fields: SigmaResumenFields;
  visorFicha?: SigmaVisorFicha | null;
  clasificacion?: SigmaClassification | null;
}) {
  const origenUser = sigmaCatalogSourceUserLabel(fields.source);
  const capaUser = sigmaLayerKindUserLabel(fields.layerKind);
  const aprobacion = formatSigmaArcgisMs(fields.aprobacionMs);

  const techRows: { label: string; value: string }[] = [];
  if (hasValue(fields.expedienteGrupo)) {
    techRows.push({ label: "Referencia municipal", value: fields.expedienteGrupo });
  }
  if (origenUser) techRows.push({ label: "Registro", value: origenUser });
  if (capaUser) techRows.push({ label: "Tipo en mapa", value: capaUser });
  if (hasValue(fields.fase)) techRows.push({ label: "Fase oficial", value: fields.fase! });
  if (hasValue(fields.denominacion)) {
    techRows.push({ label: sigmaVisorFieldLabel("denominacionVisor"), value: fields.denominacion! });
  }
  if (aprobacion) techRows.push({ label: "Fecha de aprobación", value: aprobacion });
  if (hasValue(visorFicha?.iniciativa)) {
    techRows.push({ label: sigmaVisorFieldLabel("iniciativa"), value: visorFicha!.iniciativa! });
  }
  if (hasValue(fields.organo ?? visorFicha?.unidadTramitadora)) {
    techRows.push({
      label: "Órgano tramitador",
      value: (fields.organo ?? visorFicha?.unidadTramitadora)!,
    });
  }
  if (hasValue(visorFicha?.figuraCodigo)) {
    techRows.push({ label: sigmaVisorFieldLabel("figuraCodigo"), value: visorFicha!.figuraCodigo! });
  }
  if (hasValue(visorFicha?.tipoPlaneamiento)) {
    techRows.push({
      label: sigmaVisorFieldLabel("tipoPlaneamiento"),
      value: visorFicha!.tipoPlaneamiento!,
    });
  }
  if (hasValue(visorFicha?.sistemaActuacion)) {
    techRows.push({
      label: sigmaVisorFieldLabel("sistemaActuacion"),
      value: visorFicha!.sistemaActuacion!,
    });
  }
  if (hasValue(visorFicha?.ambitoOrdenacion)) {
    techRows.push({
      label: sigmaVisorFieldLabel("ambitoOrdenacion"),
      value: visorFicha!.ambitoOrdenacion!,
    });
  }
  if (hasValue(visorFicha?.archivoPlanos)) {
    techRows.push({ label: sigmaVisorFieldLabel("archivoPlanos"), value: visorFicha!.archivoPlanos! });
  }

  if (!techRows.length) return null;

  return (
    <details className="rounded-xl border border-slate-200 bg-slate-50/40">
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-slate-600 hover:text-slate-900">
        Detalles técnicos e informes
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
  );
}

/** Resumen compacto para fichas BOCM enlazadas a SIGMA. */
export function SigmaUserResumen({
  fields,
  visorFicha,
  clasificacion,
}: {
  fields: SigmaResumenFields;
  visorFicha?: SigmaVisorFicha | null;
  clasificacion?: SigmaClassification | null;
}) {
  return (
    <div className="space-y-4">
      <SigmaInfoPublicaBanner fields={fields} />
      <SigmaTechnicalDetails
        fields={fields}
        visorFicha={visorFicha}
        clasificacion={clasificacion}
      />
    </div>
  );
}
