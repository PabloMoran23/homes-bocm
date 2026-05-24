"use client";

import Link from "next/link";
import { projectPath } from "@/lib/project-display";
import { sigmaPickDisplayHeadline, type SigmaPresentationInput } from "@/lib/sigma-presentation";
import {
  sigmaClassificationHeroToneClass,
  sigmaHeroClassificationHeadline,
} from "@/lib/sigma-classification-icon";
import { sigmaFaseShortLabel, sigmaStatusBadge } from "@/lib/sigma-user-labels";
import type { SigmaClassification } from "@/lib/sigma-classification";
import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";

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
  compact?: boolean;
}) {
  const status = sigmaStatusBadge(presentation.source);
  const { title } = sigmaPickDisplayHeadline(presentation);
  const fase = sigmaFaseShortLabel(presentation.fase);
  const classHeadline = sigmaHeroClassificationHeadline(clasificacion);

  return (
    <header className="portal-hero-bg overflow-hidden rounded-2xl border border-indigo-200/50 shadow-sm">
      <div className={compact ? "p-4 sm:p-5" : "p-5 sm:p-8"}>
        <div className="flex items-start gap-4 sm:gap-5">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-indigo-100 px-3 py-0.5 text-xs font-semibold text-indigo-950 ring-1 ring-indigo-200">
                Proyecto urbanístico · SIGMA
              </span>
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

            {classHeadline ? (
              <p
                className={`mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 ${compact ? "" : "mt-4"}`}
              >
                Tipo de proyecto
              </p>
            ) : null}

            {classHeadline ? (
              <p
                className={`mt-1 font-serif font-semibold leading-tight ${sigmaClassificationHeroToneClass(clasificacion)} ${
                  compact ? "text-xl sm:text-2xl" : "text-2xl sm:text-3xl"
                }`}
              >
                {classHeadline.title}
              </p>
            ) : null}

            <h1
              className={`font-bold leading-tight tracking-tight text-slate-900 ${
                classHeadline
                  ? compact
                    ? "mt-2 text-lg sm:text-xl"
                    : "mt-2 text-xl sm:text-2xl"
                  : compact
                    ? "mt-3 text-xl sm:text-2xl"
                    : "mt-5 text-2xl sm:text-3xl"
              }`}
            >
              {title}
            </h1>

            {classHeadline?.summary ? (
              <p
                className={`mt-2 max-w-2xl text-sm leading-relaxed text-slate-600 ${compact ? "" : "sm:text-base"}`}
              >
                {classHeadline.summary}
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

          {clasificacion ? (
            <SigmaClassificationIcon
              clasificacion={clasificacion}
              size="hero"
              className="hidden sm:flex"
            />
          ) : null}
        </div>
      </div>
    </header>
  );
}
