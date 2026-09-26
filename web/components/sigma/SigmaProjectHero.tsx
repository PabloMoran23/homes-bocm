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
    <header className="portal-hero-bg overflow-hidden rounded-2xl border border-[var(--portal-paper-deep)] shadow-sm">
      <div className={compact ? "p-4 sm:p-5" : "p-5 sm:p-8"}>
        <div className="flex min-w-0 max-w-full flex-col gap-3 sm:flex-row sm:items-start sm:gap-5">
          {clasificacion ? (
            <div className="flex shrink-0 justify-end sm:order-2">
              <SigmaClassificationIcon clasificacion={clasificacion} size="hero" />
            </div>
          ) : null}
          <div className="min-w-0 flex-1 sm:order-1">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-[var(--portal-accent-soft)] px-3 py-0.5 text-xs font-semibold text-[var(--portal-accent)] ring-1 ring-[var(--portal-accent)]/20">
                Proyecto urbanístico
              </span>
              {presentation.source === "informacion_publica" ? (
                <span className={`rounded-full px-3 py-0.5 text-xs font-semibold ${status.className}`}>
                  {status.label}
                </span>
              ) : fase ? (
                <span className="rounded-full bg-[var(--portal-paper)] px-3 py-0.5 text-xs font-semibold text-[var(--portal-accent)] ring-1 ring-[var(--portal-accent)]/20">
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
                className={`mt-1 break-words font-semibold leading-tight ${sigmaClassificationHeroToneClass(clasificacion)} ${
                  compact ? "text-lg sm:text-2xl" : "text-xl sm:text-3xl"
                }`}
              >
                {classHeadline.title}
              </p>
            ) : null}

            <h1
              className={`break-words font-bold leading-tight tracking-tight text-slate-900 ${
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
                className={`mt-2 max-w-2xl break-words text-sm leading-relaxed text-slate-600 ${compact ? "" : "sm:text-base"}`}
              >
                {classHeadline.summary}
              </p>
            ) : null}

            <div className={`flex max-w-full flex-wrap gap-2 ${compact ? "mt-4" : "mt-6"}`}>
              {visorUrl ? (
                <a
                  href={visorUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex rounded-lg bg-[var(--portal-accent)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--portal-accent-hover)]"
                >
                  Ayuntamiento ↗
                </a>
              ) : null}
              {bocmFirstId ? (
                <Link
                  href={projectPath(bocmFirstId)}
                  className="inline-flex rounded-lg border border-[var(--portal-paper-deep)] bg-[var(--portal-paper)] px-4 py-2 text-sm font-semibold text-[var(--portal-ink)] hover:bg-[var(--portal-paper-deep)]"
                >
                  Ver anuncio en el Boletín
                </Link>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
