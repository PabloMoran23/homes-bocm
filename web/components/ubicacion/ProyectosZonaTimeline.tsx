"use client";

import Link from "next/link";
import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";
import { UbicacionExpedientePresentacion } from "@/components/ubicacion/UbicacionExpedientePresentacion";
import {
  fechaDestacadaUbicacionExpediente,
  faseEnLenguajeClaro,
  ordenarExpedientesPorFecha,
} from "@/lib/ubicacion-resumen";
import type { SigmaClassification } from "@/lib/sigma-classification";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import type { UbicacionSigmaExpediente, UbicacionTramite } from "@/lib/ubicacion";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";

export function ProyectosZonaTimeline({
  expedientes,
  tramitacionSigma,
  metricsByExpediente = {},
  clasificacionByExpediente = {},
}: {
  expedientes: UbicacionSigmaExpediente[];
  tramitacionSigma: Record<string, UbicacionTramite[]>;
  metricsByExpediente?: Record<string, SigmaExpedienteMetric | null>;
  clasificacionByExpediente?: Record<string, SigmaClassification | null>;
}) {
  const ordenados = ordenarExpedientesPorFecha(expedientes, tramitacionSigma);
  const conFecha = ordenados.filter((exp) => {
    const { fechaSort } = fechaDestacadaUbicacionExpediente(
      exp,
      tramitacionSigma[exp.expediente_grupo] || [],
    );
    return fechaSort > 0;
  });

  if (conFecha.length === 0) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-slate-800">Cronología de aprobaciones en la zona</h3>
      <p className="mt-1 text-xs text-slate-500">
        Ordenados de más antiguo a más reciente según la fecha clave de cada proyecto.
      </p>
      <div
        className="mt-4 overflow-x-auto overscroll-x-contain pb-2 [-ms-overflow-style:none] [scrollbar-width:thin] [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-sky-300/80"
        role="region"
        aria-label="Cronología de proyectos en la zona"
      >
        <div className="relative min-w-min px-1 pt-1">
          <div
            className="pointer-events-none absolute top-4 right-8 left-8 h-0.5 bg-sky-200/90"
            aria-hidden
          />
          <ol className="relative flex snap-x snap-mandatory gap-0">
            {conFecha.map((exp, i) => {
              const tram = tramitacionSigma[exp.expediente_grupo] || [];
              const { fecha, hitoLabel, soloAnio } = fechaDestacadaUbicacionExpediente(exp, tram);
              const clasificacion = clasificacionByExpediente[exp.expediente_grupo] ?? null;
              const metric = metricsByExpediente[exp.expediente_grupo] ?? null;
              const isLast = i === conFecha.length - 1;

              return (
                <li
                  key={exp.expediente_grupo}
                  className={`relative flex min-w-[14rem] max-w-[16rem] shrink-0 snap-start flex-col px-2 sm:min-w-[15rem] sm:max-w-[17rem] ${i === 0 ? "pl-0" : ""} ${isLast ? "pr-0" : ""}`}
                >
                  <div className="flex justify-center pb-3" aria-hidden>
                    <div className="relative z-10">
                      <SigmaClassificationIcon clasificacion={clasificacion} size="sm" />
                    </div>
                  </div>
                  <Link
                    href={sigmaFichaPath(exp.expediente_grupo)}
                    className="flex flex-1 flex-col rounded-xl border border-sky-100 bg-sky-50/40 p-3 shadow-sm transition hover:border-sky-200 hover:bg-sky-50/70"
                  >
                    {fecha ? (
                      <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                        <time
                          dateTime={soloAnio ? `${fecha}-01-01` : undefined}
                          className="text-xs font-semibold tabular-nums text-slate-800"
                        >
                          {fecha}
                        </time>
                        {hitoLabel ? (
                          <span className="text-[10px] font-medium text-sky-800">{hitoLabel}</span>
                        ) : null}
                      </div>
                    ) : null}
                    <UbicacionExpedientePresentacion
                      exp={exp}
                      metric={metric}
                      clasificacion={clasificacion}
                      compact
                      showIcon={false}
                    />
                    <p className="mt-2 text-[11px] text-slate-500">{faseEnLenguajeClaro(exp.fase)}</p>
                  </Link>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </div>
  );
}
