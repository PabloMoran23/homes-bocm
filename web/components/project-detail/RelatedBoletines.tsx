import Link from "next/link";
import type { SigmaBoletinMencion } from "@/lib/types";
import { hasValue, projectPath } from "@/lib/project-display";

export function RelatedBoletines({ rows }: { rows: SigmaBoletinMencion[] }) {
  if (!rows.length) return null;

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-3 py-2.5">Fecha</th>
            <th className="px-3 py-2.5">Art.</th>
            <th className="px-3 py-2.5">Titular</th>
            <th className="px-3 py-2.5">Estado BOCM</th>
            <th className="px-3 py-2.5">Instrumento</th>
            <th className="px-3 py-2.5 text-center">PDF</th>
            <th className="px-3 py-2.5 text-center">Ficha</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((m) => (
            <tr
              key={m.projectId}
              className={m.mismoAnuncioQueEstaVista ? "bg-teal-50/60" : "bg-white"}
            >
              <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-700">
                {m.bocmDate || "—"}
              </td>
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{m.artNum || "—"}</td>
              <td className="max-w-[240px] px-3 py-2 text-xs text-slate-800">
                {m.title?.slice(0, 140) || "—"}
                {m.title && m.title.length > 140 ? "…" : ""}
                {m.mismoAnuncioQueEstaVista ? (
                  <span className="ml-2 inline-block rounded bg-teal-200/90 px-1.5 py-0 text-[10px] font-bold uppercase text-teal-950">
                    Este anuncio
                  </span>
                ) : null}
              </td>
              <td className="px-3 py-2 text-xs">{m.estadoTramitacion || "—"}</td>
              <td className="max-w-[120px] truncate px-3 py-2 text-xs text-slate-600">
                {m.tipoInstrumento || "—"}
              </td>
              <td className="px-3 py-2 text-center">
                {hasValue(m.pdfUrl) ? (
                  <a
                    href={m.pdfUrl!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-semibold text-teal-700 hover:underline"
                  >
                    PDF
                  </a>
                ) : (
                  <span className="text-slate-300">—</span>
                )}
              </td>
              <td className="px-3 py-2 text-center">
                <Link
                  href={projectPath(m.projectId)}
                  prefetch={false}
                  className="text-xs font-semibold text-[var(--portal-accent)] hover:underline"
                >
                  Abrir
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
