"use client";

import Link from "next/link";
import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";
import {
  sigmaClassificationHeroToneClass,
  sigmaHeroClassificationHeadline,
} from "@/lib/sigma-classification-icon";
import type { SigmaClassification } from "@/lib/sigma-classification";
import {
  sigmaProgramaRolLabel,
  type SigmaPrograma,
  type SigmaProgramaExpedienteRef,
} from "@/lib/sigma-programa";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";

export function SigmaProgramaPanel({
  programa,
  expedienteActual,
  refActual,
  clasificacionByExpediente = {},
  compact = false,
}: {
  programa: SigmaPrograma;
  expedienteActual: string;
  refActual?: SigmaProgramaExpedienteRef | null;
  clasificacionByExpediente?: Record<string, SigmaClassification | null>;
  compact?: boolean;
}) {
  const miembros = [...programa.miembros].sort((a, b) => a.ordenFase - b.ordenFase);
  if (miembros.length < 2) return null;

  const rolActual = refActual?.rol ?? miembros.find((m) => m.expedienteGrupo === expedienteActual)?.rol;
  const rango =
    programa.anioInicio && programa.anioFin && programa.anioInicio !== programa.anioFin
      ? `${programa.anioInicio}–${programa.anioFin}`
      : programa.anioInicio
        ? String(programa.anioInicio)
        : null;

  const cardMin = compact
    ? "min-w-[12rem] max-w-[14rem]"
    : "min-w-[14rem] max-w-[16rem] sm:min-w-[15rem] sm:max-w-[17rem]";

  return (
    <section
      className={`overflow-hidden rounded-2xl border border-indigo-200/70 bg-indigo-50/35 ${compact ? "" : "shadow-sm"}`}
      aria-labelledby="sigma-programa-heading"
    >
      <header className="border-b border-indigo-100/80 px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-950">
            Programa urbanístico
          </span>
          {programa.confianza === "alta" ? (
            <span className="rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-teal-800 ring-1 ring-teal-200">
              Mismo ámbito
            </span>
          ) : (
            <span className="rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-slate-600 ring-1 ring-slate-200">
              Agrupación estimada
            </span>
          )}
          {rango ? <span className="text-[11px] tabular-nums text-slate-500">{rango}</span> : null}
        </div>
        <h2 id="sigma-programa-heading" className="mt-2 text-base font-semibold leading-snug text-slate-900">
          {programa.titulo}
        </h2>
        {programa.ambitoOrdenacion ? (
          <p className="mt-1 text-xs text-indigo-800/80">Ámbito {programa.ambitoOrdenacion}</p>
        ) : null}
        {rolActual ? (
          <p className="mt-2 text-sm text-slate-700">
            <span className="font-semibold text-indigo-950">Este expediente</span> corresponde a la fase de{" "}
            <span className="font-semibold text-indigo-900">{sigmaProgramaRolLabel(rolActual)}</span> dentro del
            programa ({miembros.length} expedientes enlazados).
          </p>
        ) : null}
        <p className="mt-1 text-xs text-slate-500">
          El Ayuntamiento los tramita por separado; la línea siguiente ordena las fases del mismo proceso.
        </p>
      </header>

      <div className="px-4 py-4 sm:px-5">
        <div
          className="overflow-x-auto overscroll-x-contain pb-2 [-ms-overflow-style:none] [scrollbar-width:thin] [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-indigo-300/80"
          role="region"
          aria-label="Fases del programa urbanístico"
        >
          <div className="relative min-w-min px-1 pt-1">
            <div
              className="pointer-events-none absolute top-4 right-8 left-8 h-0.5 bg-indigo-200/90"
              aria-hidden
            />
            <ol className="relative flex snap-x snap-mandatory gap-0">
              {miembros.map((m, i) => {
                const esActual = m.expedienteGrupo === expedienteActual;
                const isLast = i === miembros.length - 1;
                const clasificacion = clasificacionByExpediente[m.expedienteGrupo] ?? null;
                const classHeadline = sigmaHeroClassificationHeadline(clasificacion);
                const classificationTitle =
                  classHeadline?.title ?? sigmaProgramaRolLabel(m.rol);
                const anio = m.anio ? String(m.anio) : null;
                const fichaHref = sigmaFichaPath(m.expedienteGrupo);

                return (
                  <li
                    key={m.expedienteGrupo}
                    className={`relative flex shrink-0 snap-start flex-col px-2 ${cardMin} ${i === 0 ? "pl-0" : ""} ${isLast ? "pr-0" : ""}`}
                  >
                    <div className="flex justify-center pb-3" aria-hidden>
                      <div className={`relative z-10 ${esActual ? "scale-110" : ""}`}>
                        <SigmaClassificationIcon clasificacion={clasificacion} size="sm" />
                      </div>
                    </div>
                    <div
                      className={`flex flex-1 flex-col rounded-xl border p-3 shadow-sm ${
                        esActual
                          ? "border-indigo-400 bg-white ring-2 ring-indigo-300/80"
                          : "border-indigo-100/90 bg-white/90"
                      }`}
                    >
                      {esActual ? (
                        <span className="mb-2 w-fit rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                          Este expediente
                        </span>
                      ) : null}
                      {anio ? (
                        <time dateTime={`${anio}-01-01`} className="text-sm font-bold tabular-nums text-slate-800">
                          {anio}
                        </time>
                      ) : null}
                      <div className={anio ? "mt-2" : ""}>
                        <p
                          className={`break-words font-semibold leading-tight ${sigmaClassificationHeroToneClass(clasificacion)} text-sm`}
                        >
                          {classificationTitle}
                        </p>
                        <p className="mt-1 line-clamp-3 text-xs font-bold leading-snug text-slate-900">
                          {m.denominacion || m.expedienteGrupo}
                        </p>
                      </div>
                      {!esActual ? (
                        <Link
                          href={fichaHref}
                          className="mt-3 inline-flex text-xs font-semibold text-indigo-700 hover:underline"
                        >
                          Ver ficha del proyecto →
                        </Link>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
