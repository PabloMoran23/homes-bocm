"use client";

import Link from "next/link";
import { projectPath } from "@/lib/project-display";
import { sigmaPickDisplayHeadline, type SigmaPresentationInput } from "@/lib/sigma-presentation";
import {
  sigmaClassificationLabel,
  sigmaClassificationTone,
  type SigmaClassification,
} from "@/lib/sigma-classification";
import { sigmaFaseShortLabel, sigmaStatusBadge } from "@/lib/sigma-user-labels";

export function SigmaProjectHero({
  presentation,
  clasificacion,
  visorUrl,
  bocmFirstId,
  bocmCount = 0,
  compact = false,
}: {
  presentation: SigmaPresentationInput;
  clasificacion?: SigmaClassification | null;
  visorUrl?: string | null;
  bocmFirstId?: string | null;
  bocmCount?: number;
  /** Menos padding y texto acortado para caber junto al mapa. */
  compact?: boolean;
}) {
  const status = sigmaStatusBadge(presentation.source);
  const { title, subtitle } = sigmaPickDisplayHeadline(presentation);
  const fase = sigmaFaseShortLabel(presentation.fase);
  const category = sigmaClassificationLabel(clasificacion?.categoriaProyecto);
  const categoryTone = sigmaClassificationTone(clasificacion?.categoriaProyecto);
  const categoryClass = {
    teal: "bg-teal-100 text-teal-900",
    violet: "bg-violet-50 text-violet-900 ring-1 ring-violet-200",
    amber: "bg-amber-50 text-amber-900 ring-1 ring-amber-200",
    sky: "bg-sky-50 text-sky-900 ring-1 ring-sky-200",
    slate: "bg-slate-100 text-slate-700",
  }[categoryTone];

  return (
    <header className="portal-hero-bg overflow-hidden rounded-2xl border border-teal-200/50 shadow-sm">
      <div className={compact ? "p-4 sm:p-5" : "p-5 sm:p-8"}>
        <div className="flex flex-wrap gap-2">
          {category ? (
            <span className={`rounded-full px-3 py-0.5 text-xs font-semibold ${categoryClass}`}>
              {category}
            </span>
          ) : null}
          {presentation.source === "informacion_publica" ? (
            <span className={`rounded-full px-3 py-0.5 text-xs font-semibold ${status.className}`}>
              {status.label}
            </span>
          ) : fase ? (
            <span className="rounded-full bg-sky-50 px-3 py-0.5 text-xs font-semibold text-sky-900 ring-1 ring-sky-200">
              {fase}
            </span>
          ) : null}
        </div>

        <h1
          className={`mt-3 font-bold leading-tight tracking-tight text-slate-900 ${
            compact ? "text-xl sm:text-2xl" : "mt-5 text-2xl sm:text-3xl"
          }`}
        >
          {title}
        </h1>
        {subtitle ? (
          <p
            className={`mt-1.5 font-medium text-teal-900/90 ${compact ? "text-sm" : "text-base"}`}
          >
            {subtitle}
          </p>
        ) : null}

        <div className={`flex flex-wrap gap-2 ${compact ? "mt-4" : "mt-6"}`}>
          {visorUrl ? (
            <a
              href={visorUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex rounded-lg bg-[var(--portal-accent)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--portal-accent-hover)]"
            >
              Visor municipal ↗
            </a>
          ) : null}
          {bocmFirstId ? (
            <Link
              href={projectPath(bocmFirstId)}
              className="inline-flex rounded-lg border border-teal-300 bg-white px-4 py-2 text-sm font-semibold text-teal-950 hover:bg-teal-50"
            >
              Ver anuncio en el Boletín
            </Link>
          ) : null}
        </div>
      </div>
    </header>
  );
}
