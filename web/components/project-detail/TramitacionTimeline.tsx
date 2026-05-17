"use client";

import type { SigmaVisorTramite } from "@/lib/types";
import { tramiteBadgeClass, tramiteDotClass, tramiteKind } from "@/lib/tramite-style";

export function TramitacionTimeline({ rows }: { rows: SigmaVisorTramite[] }) {
  if (!rows.length) return null;

  return (
    <ol className="relative space-y-0 border-l-2 border-teal-200/80 pl-6">
      {rows.map((row, i) => {
        const kind = tramiteKind(row.tramite);
        return (
          <li key={`${row.fecha}-${row.tramite}-${i}`} className="relative pb-8 last:pb-0">
            <span
              className={`absolute -left-[1.6rem] top-1.5 h-3 w-3 rounded-full ring-4 ${tramiteDotClass(kind)}`}
              aria-hidden
            />
            <div className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                {row.fecha ? (
                  <time className="text-sm font-semibold tabular-nums text-slate-800">
                    {row.fecha}
                  </time>
                ) : (
                  <span className="text-sm text-slate-400">Sin fecha</span>
                )}
                {row.tramite ? (
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${tramiteBadgeClass(kind)}`}
                  >
                    {row.tramite}
                  </span>
                ) : null}
              </div>
              {row.organo ? (
                <p className="mt-2 text-sm text-slate-600">
                  <span className="font-medium text-slate-500">Órgano · </span>
                  {row.organo}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
