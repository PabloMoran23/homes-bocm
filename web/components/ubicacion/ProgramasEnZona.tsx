"use client";

import Link from "next/link";
import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";
import { UbicacionExpedientePresentacion } from "@/components/ubicacion/UbicacionExpedientePresentacion";
import { ordenarMiembrosProgramaCronologico } from "@/lib/sigma-programa-timeline";
import type { SigmaClassification } from "@/lib/sigma-classification";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import type { SigmaPrograma } from "@/lib/sigma-programa";
import type { UbicacionSigmaExpediente, UbicacionTramite } from "@/lib/ubicacion";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";

export function ProgramasEnZona({
  programas,
  expedientesByGrupo,
  tramitacionSigma,
  metricsByExpediente = {},
  clasificacionByExpediente = {},
}: {
  programas: SigmaPrograma[];
  expedientesByGrupo: Record<string, UbicacionSigmaExpediente>;
  tramitacionSigma: Record<string, UbicacionTramite[]>;
  metricsByExpediente?: Record<string, SigmaExpedienteMetric | null>;
  clasificacionByExpediente?: Record<string, SigmaClassification | null>;
}) {
  if (!programas.length) return null;

  return (
    <div className="space-y-6">
      {programas.map((prog) => {
        const miembros = ordenarMiembrosProgramaCronologico(prog.miembros, {
          expedientesByGrupo,
          tramitacionSigma,
        })
          .map(({ miembro, anio }) => {
            const exp = expedientesByGrupo[miembro.expedienteGrupo];
            if (!exp) return null;
            return {
              exp,
              miembro,
              anio,
              clasificacion: clasificacionByExpediente[miembro.expedienteGrupo] ?? null,
              metric: metricsByExpediente[miembro.expedienteGrupo] ?? null,
            };
          })
          .filter(Boolean) as {
          exp: UbicacionSigmaExpediente;
          miembro: (typeof prog.miembros)[number];
          anio: string | null;
          clasificacion: SigmaClassification | null;
          metric: SigmaExpedienteMetric | null;
        }[];

        if (miembros.length < 2) return null;

        return (
          <article
            key={prog.programaId}
            className="overflow-hidden rounded-2xl border border-indigo-200/70 bg-indigo-50/35 shadow-sm"
          >
            <header className="border-b border-indigo-100/80 px-4 py-4 sm:px-5">
              <h3 className="text-base font-semibold leading-snug text-slate-900 sm:text-lg">
                {prog.titulo}
              </h3>
            </header>

            <div className="px-4 py-4 sm:px-5">
              <div
                className="overflow-x-auto overscroll-x-contain pb-2 [-ms-overflow-style:none] [scrollbar-width:thin] [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-indigo-300/80"
                role="region"
                aria-label={`Cronología de ${prog.titulo}`}
              >
                <div className="relative min-w-min px-1 pt-1">
                  <div
                    className="pointer-events-none absolute top-4 right-8 left-8 h-0.5 bg-indigo-200/90"
                    aria-hidden
                  />
                  <ol className="relative flex snap-x snap-mandatory gap-0">
                    {miembros.map((m, i) => {
                        const isLast = i === miembros.length - 1;
                        const fichaHref = sigmaFichaPath(m.exp.expediente_grupo);
                        return (
                          <li
                            key={m.exp.expediente_grupo}
                            className={`relative flex min-w-[14rem] max-w-[16rem] shrink-0 snap-start flex-col px-2 sm:min-w-[15rem] sm:max-w-[17rem] ${i === 0 ? "pl-0" : ""} ${isLast ? "pr-0" : ""}`}
                          >
                            <div className="flex justify-center pb-3" aria-hidden>
                              <div className="relative z-10">
                                <SigmaClassificationIcon
                                  clasificacion={m.clasificacion}
                                  size="sm"
                                />
                              </div>
                            </div>
                            <div className="flex flex-1 flex-col rounded-xl border border-indigo-100/90 bg-white/90 p-3 shadow-sm">
                              {m.anio ? (
                                <time
                                  dateTime={`${m.anio}-01-01`}
                                  className="text-sm font-bold tabular-nums text-slate-800"
                                >
                                  {m.anio}
                                </time>
                              ) : null}
                              <div className={m.anio ? "mt-2" : ""}>
                                <UbicacionExpedientePresentacion
                                  exp={m.exp}
                                  metric={m.metric}
                                  clasificacion={m.clasificacion}
                                  compact
                                  showIcon={false}
                                />
                              </div>
                              <Link
                                href={fichaHref}
                                className="mt-3 inline-flex text-xs font-semibold text-indigo-700 hover:underline"
                              >
                                Ver ficha del proyecto →
                              </Link>
                            </div>
                          </li>
                        );
                      })}
                  </ol>
                </div>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
