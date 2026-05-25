"use client";

import type { SigmaPromotorTableRow } from "@/lib/sigma-promotores-table";

const COLUMNS: { key: keyof SigmaPromotorTableRow; label: string; title?: string }[] = [
  { key: "total", label: "Total" },
  { key: "vivienda", label: "Vivienda", title: "Proyectos con señal residencial" },
  { key: "urbanismo", label: "Urbanismo", title: "Urbanización, redes o proyecto de urbanización" },
  { key: "privada", label: "Privada", title: "Iniciativa privada (ficha municipal)" },
  { key: "municipal", label: "Municipal", title: "Iniciativa municipal (ficha municipal)" },
];

export function SigmaPromotoresTable({ rows }: { rows: SigmaPromotorTableRow[] }) {
  if (!rows.length) {
    return (
      <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-5 text-center text-xs text-slate-500">
        Sin promotor en la ficha municipal para los filtros actuales.
      </p>
    );
  }

  return (
    <div className="max-w-2xl overflow-x-auto rounded-lg border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.03]">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50/80">
            <th className="px-2.5 py-1.5 font-semibold uppercase tracking-wide text-slate-500">
              Promotor
            </th>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                title={col.title}
                className="w-14 px-1.5 py-1.5 text-right font-semibold uppercase tracking-wide text-slate-500"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-slate-50/60">
              <td className="max-w-[11rem] px-2.5 py-1 font-medium text-slate-900">
                <span className="line-clamp-2 leading-snug" title={row.label}>
                  {row.label}
                </span>
              </td>
              {COLUMNS.map((col) => (
                <td
                  key={col.key}
                  className="px-1.5 py-1 text-right tabular-nums text-slate-600"
                >
                  {row[col.key].toLocaleString("es-ES")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
