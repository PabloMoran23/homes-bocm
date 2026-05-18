"use client";

import { hasValue } from "@/lib/project-display";
import type { SigmaVisorFicha } from "@/lib/types";

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex max-w-full items-center rounded-full bg-white/90 px-2.5 py-0.5 text-xs font-medium text-teal-950 ring-1 ring-teal-200/80">
      <span className="truncate">{children}</span>
    </span>
  );
}

export function SigmaVisorFichaHighlights({ ficha }: { ficha: SigmaVisorFicha }) {
  const sup =
    ficha.superficieAmbitoM2 != null && ficha.superficieAmbitoM2 > 0
      ? `${ficha.superficieAmbitoM2.toLocaleString("es-ES")} m²`
      : ficha.superficieAmbitoTexto;

  const chips: string[] = [];
  if (hasValue(ficha.figuraTipo)) chips.push(ficha.figuraTipo);
  if (hasValue(ficha.tipoPlaneamiento)) chips.push(ficha.tipoPlaneamiento);
  if (hasValue(ficha.distrito)) chips.push(ficha.distrito);
  if (hasValue(sup)) chips.push(sup);
  if (hasValue(ficha.promotor)) {
    const p = ficha.promotor.trim();
    chips.push(p.length > 42 ? `${p.slice(0, 41)}…` : p);
  }
  if (hasValue(ficha.iniciativa)) chips.push(`Iniciativa ${ficha.iniciativa.toLowerCase()}`);

  if (!chips.length) return null;

  return (
    <div className="mt-2.5 flex flex-wrap gap-1.5">
      {chips.map((c) => (
        <Chip key={c}>{c}</Chip>
      ))}
    </div>
  );
}
