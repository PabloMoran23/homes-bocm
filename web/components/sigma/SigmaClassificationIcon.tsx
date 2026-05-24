"use client";

import { sigmaObraIconConfig } from "@/lib/sigma-classification-icon";
import type { SigmaClassification } from "@/lib/sigma-classification";

export function SigmaClassificationIcon({
  clasificacion,
  size = "md",
  className = "",
}: {
  clasificacion?: Pick<SigmaClassification, "tipoObra" | "categoriaProyecto"> | null;
  size?: "md" | "hero";
  className?: string;
}) {
  const cfg = sigmaObraIconConfig(clasificacion);
  const px = size === "hero" ? 88 : 52;
  const svgPx = Math.round(px * 0.5);
  const svg = cfg.svg.replace("<svg ", `<svg width="${svgPx}" height="${svgPx}" `);

  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-2xl ring-1 ring-inset ring-white/30 ${className}`}
      style={{
        width: px,
        height: px,
        background: cfg.bg,
        boxShadow: `0 8px 24px ${cfg.bg}44, 0 2px 6px rgba(15,23,42,0.12)`,
      }}
      aria-hidden
    >
      <span className="flex items-center justify-center" dangerouslySetInnerHTML={{ __html: svg }} />
    </div>
  );
}
