"use client";

import { sigmaObraIconConfig } from "@/lib/sigma-classification-icon";
import type { SigmaClassification } from "@/lib/sigma-classification";

const BOX_CLASS: Record<"sm" | "md" | "hero", string> = {
  sm: "h-8 w-8 min-h-8 min-w-8 rounded-lg",
  md: "h-[3.25rem] w-[3.25rem] sm:h-[3.25rem] sm:w-[3.25rem]",
  hero: "h-10 w-10 min-h-10 min-w-10 sm:h-14 sm:w-14 md:h-[4.5rem] md:w-[4.5rem] lg:h-[5.5rem] lg:w-[5.5rem]",
};

const ICON_CLASS: Record<"sm" | "md" | "hero", string> = {
  sm: "h-4 w-4",
  md: "h-[1.625rem] w-[1.625rem]",
  hero: "h-5 w-5 sm:h-7 sm:w-7 md:h-9 md:w-9 lg:h-11 lg:w-11",
};

export function SigmaClassificationIcon({
  clasificacion,
  size = "md",
  className = "",
}: {
  clasificacion?: Pick<SigmaClassification, "tipoObra" | "categoriaProyecto"> | null;
  size?: "sm" | "md" | "hero";
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
