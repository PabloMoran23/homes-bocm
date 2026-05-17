"use client";

import { usePathname } from "next/navigation";

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
          <strong className="font-semibold text-slate-800">Homes · Urbanismo</strong> te acerca lo que
          importa del planeamiento alrededor de tu zona: seguimiento de proyectos, lectura clara y
          herramientas para comparar y reaccionar a tiempo. No publicamos el detalle de nuestras
          fuentes; detrás hay más de mil señales distintas que unificamos para ti.
        </p>
        <p className="leading-relaxed">
          Cuando un proyecto tiene documentación pública asociada, te damos acceso directo desde la
          ficha. Homes no sustituye el criterio técnico ni legal de un arquitecto, aparejador o
          abogado.
        </p>
        <p className="text-xs text-slate-500">
          Coordenadas aproximadas por municipio (centroide). No sustituye la cartografía urbanística
          ni los visores del ayuntamiento.
        </p>
      </div>
    </footer>
  );
}
