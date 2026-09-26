"use client";

import { useState } from "react";
import type { CmPortalProyectoProps } from "@/lib/cm-portal-geo";

function formatFecha(fecha?: string): string {
  if (!fecha || !/^\d{4}-\d{2}-\d{2}$/.test(fecha)) return "";
  const [year, month, day] = fecha.split("-").map(Number);
  const name = new Date(year, month - 1, day).toLocaleDateString("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return name.replace(".", "");
}

export function PortalOtrosProyectos({
  nombre,
  features,
  total,
}: {
  nombre: string;
  features: Array<{ properties: CmPortalProyectoProps }>;
  total: number;
}) {
  const [open, setOpen] = useState(false);
  if (!features.length && total <= 0) return null;
  const shown = features.length;
  const count = Math.max(total, shown);
  const hasExtent = features.some((feature) => feature.properties.fueraDeMapa === "extension");
  const hasNoCoord = features.some((feature) => feature.properties.fueraDeMapa !== "extension");

  return (
    <div className="absolute bottom-20 left-3 z-[1100] flex w-[min(100%-1.5rem,22rem)] flex-col-reverse items-start sm:bottom-16 sm:left-auto sm:right-4 sm:items-end">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="rounded-full border border-white/90 bg-white/95 px-3 py-1.5 text-sm font-semibold text-slate-800 shadow-lg"
        aria-expanded={open}
      >
        Otros proyectos · {count.toLocaleString("es-ES")}
      </button>
      {open ? (
        <div className="mb-2 overflow-hidden rounded-2xl border border-[#ebe4d6] bg-[#f7f3eb] shadow-xl">
          <p className="px-3 pt-3 text-xs leading-relaxed text-[#2a2622]/80">
            {hasExtent && hasNoCoord
              ? `Proyectos de ${nombre} que no se dibujan: unos no tienen coordenada exacta y otros cubren tanta extensión que taparían el municipio.`
              : hasExtent
                ? `Proyectos de ${nombre} que cubren tanta extensión que taparían el mapa.`
                : `Sin parcela en el mapa. Son proyectos de ${nombre}, sin coordenada exacta.`}
            {count > shown ? ` Mostramos ${shown.toLocaleString("es-ES")} de ${count.toLocaleString("es-ES")}.` : ""}
          </p>
          <ul className="max-h-64 overflow-y-auto px-1 py-2">
            {features.map((feature) => {
              const p = feature.properties;
              const fecha = formatFecha(p.fecha);
              return (
                <li key={p.id}>
                  <a
                    href={`/proyecto/${encodeURIComponent(p.id)}`}
                    className="block rounded-xl px-2 py-2 hover:bg-white"
                  >
                    <span className="line-clamp-2 text-sm font-semibold leading-snug text-[#2a2622]">
                      {p.titulo || p.id}
                    </span>
                    {fecha || p.fueraDeMapa === "extension" ? (
                      <span className="mt-0.5 block text-[11px] font-medium text-[#1f4f53]">
                        {p.fueraDeMapa === "extension" ? "Cubre demasiado terreno para dibujarlo" : null}
                        {p.fueraDeMapa === "extension" && fecha ? " · " : null}
                        {fecha || null}
                      </span>
                    ) : null}
                  </a>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
