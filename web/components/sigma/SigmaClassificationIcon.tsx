"use client";

import { sigmaObraIconConfig } from "@/lib/sigma-classification-icon";
import type { SigmaClassification } from "@/lib/sigma-classification";

const BOX_CLASS: Record<"md" | "hero", string> = {
  md: "h-[3.25rem] w-[3.25rem] sm:h-[3.25rem] sm:w-[3.25rem]",
  hero: "h-12 w-12 min-h-12 min-w-12 sm:h-16 sm:w-16 md:h-20 md:w-20 lg:h-[5.5rem] lg:w-[5.5rem]",
};

const ICON_CLASS: Record<"md" | "hero", string> = {
  md: "h-[1.625rem] w-[1.625rem]",
  hero: "h-6 w-6 sm:h-8 sm:w-8 md:h-10 md:w-10 lg:h-11 lg:w-11",
};

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

  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-xl ring-1 ring-inset ring-white/30 sm:rounded-2xl ${BOX_CLASS[size]} ${className}`}
      style={{
        background: cfg.bg,
        boxShadow: `0 8px 24px ${cfg.bg}44, 0 2px 6px rgba(15,23,42,0.12)`,
      }}
      aria-hidden
    >
      <span
        className={`flex items-center justify-center [&_svg]:block ${ICON_CLASS[size]}`}
        dangerouslySetInnerHTML={{ __html: cfg.svg }}
      />
    </div>
  );
}
