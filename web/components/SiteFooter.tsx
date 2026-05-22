"use client";

import { usePathname } from "next/navigation";
import { isPublicEdition } from "@/lib/edition";

const FULL_BLEED_PREFIXES = ["/explore", "/boletin"];

export function SiteFooter() {
  const pathname = usePathname();
  const hidden = FULL_BLEED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );

  if (hidden) {
    return null;
  }

  return (
    <footer className="mt-auto border-t border-slate-200 bg-slate-50/90 py-8 text-sm text-slate-600">
      <div className="mx-auto max-w-6xl space-y-4 px-4 sm:px-6">
        <p className="leading-relaxed">
          <strong className="font-semibold text-slate-800">Homes · Urbanismo</strong>{" "}
          {isPublicEdition()
            ? "concentra licencias, expedientes SIGMA y anuncios del BOCM en un mapa y fichas legibles para Madrid capital. Versión beta: más herramientas en camino."
            : "te acerca lo que importa del planeamiento alrededor de tu zona: seguimiento de proyectos, lectura clara y herramientas para comparar y reaccionar a tiempo."}
        </p>
      </div>
    </footer>
  );
}
