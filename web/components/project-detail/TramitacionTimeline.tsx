"use client";

import type { SigmaVisorTramite } from "@/lib/types";
import { tramiteShortLabel } from "@/lib/sigma-user-labels";
import { tramiteBadgeClass, tramiteDotClass, tramiteKind } from "@/lib/tramite-style";

export function TramitacionTimeline({
  rows,
  compact,
}: {
  rows: SigmaVisorTramite[];
  /** Tarjetas más estrechas (vista previa en resumen). */
  compact?: boolean;
}) {
  if (!rows.length) return null;

  const cardMin = compact ? "min-w-[11.5rem] max-w-[13rem]" : "min-w-[13rem] max-w-[15rem] sm:min-w-[14rem]";

  return (
    <div
      className="overflow-x-auto overscroll-x-contain pb-2 [-ms-overflow-style:none] [scrollbar-width:thin] [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-300/80"
      role="region"
      aria-label="Cronología de tramitación"
    >
      <div className="relative min-w-min px-1 pt-1">
        <div
          className="pointer-events-none absolute top-[0.65rem] right-6 left-6 h-0.5 bg-teal-200/90"
          aria-hidden
        />
        <ol className="relative flex snap-x snap-mandatory gap-0">
          {rows.map((row, i) => {
            const kind = tramiteKind(row.tramite);
            const tramiteLabel = tramiteShortLabel(row.tramite);
            const isLast = i === rows.length - 1;
            return (
              <li
                key={`${row.fecha}-${row.tramite}-${i}`}
                className={`relative flex shrink-0 snap-start flex-col px-2 ${cardMin} ${i === 0 ? "pl-0" : ""} ${isLast ? "pr-0" : ""}`}
              >
                <div className="flex justify-center pb-3" aria-hidden>
                  <span
                    className={`relative z-10 h-3 w-3 rounded-full ring-4 ${tramiteDotClass(kind)}`}
                  />
                </div>
                <article
                  className={`flex flex-1 flex-col rounded-xl border border-slate-200/90 bg-white shadow-sm ${
                    compact ? "p-3" : "p-4"
                  }`}
                >
                  {row.fecha ? (
                    <time
                      dateTime={row.fecha}
                      className={`font-semibold tabular-nums text-slate-800 ${compact ? "text-xs" : "text-sm"}`}
                    >
                      {row.fecha}
                    </time>
                  ) : (
                    <span className={`text-slate-400 ${compact ? "text-xs" : "text-sm"}`}>
                      Sin fecha
                    </span>
                  )}
                  {tramiteLabel ? (
                    <span
                      title={row.tramite ?? undefined}
                      className={`mt-2 inline-flex w-fit rounded-full px-2.5 py-0.5 font-semibold ring-1 ${tramiteBadgeClass(kind)} ${compact ? "text-[10px]" : "text-xs"}`}
                    >
                      {tramiteLabel}
                    </span>
                  ) : null}
                  {row.organo ? (
                    <p className={`mt-auto pt-2 leading-snug text-slate-600 ${compact ? "text-[11px]" : "text-xs"}`}>
                      <span className="font-medium text-slate-500">Órgano · </span>
                      {row.organo}
                    </p>
                  ) : null}
                </article>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
