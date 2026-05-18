"use client";

import Link from "next/link";
import { projectPath } from "@/lib/project-display";
import { SigmaQueImplicaBlock } from "@/components/sigma/SigmaQueImplicaBlock";
import { SigmaVisorFichaHighlights } from "@/components/sigma/SigmaVisorFichaHighlights";
import {
  buildSigmaProjectLead,
  sigmaPickDisplayHeadline,
  sigmaPresentationMetaLine,
  type SigmaPresentationInput,
} from "@/lib/sigma-presentation";
import { sigmaFaseLabel, sigmaStatusBadge } from "@/lib/sigma-user-labels";

export function SigmaProjectHero({
  presentation,
  visorUrl,
  bocmFirstId,
  bocmCount = 0,
  compact = false,
}: {
  presentation: SigmaPresentationInput;
  visorUrl?: string | null;
  bocmFirstId?: string | null;
  bocmCount?: number;
  /** Menos padding y texto acortado para caber junto al mapa. */
  compact?: boolean;
}) {
  const status = sigmaStatusBadge(presentation.source);
  const { title, subtitle } = sigmaPickDisplayHeadline(presentation);
  const lead = buildSigmaProjectLead({ ...presentation, bocmCount });
  const meta = sigmaPresentationMetaLine(presentation);
  const fase = sigmaFaseLabel(presentation.fase);

  return (
    <header className="portal-hero-bg overflow-hidden rounded-2xl border border-teal-200/50 shadow-sm">
      <div className={compact ? "p-4 sm:p-5" : "p-5 sm:p-8"}>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full bg-teal-100 px-3 py-0.5 text-xs font-semibold text-teal-900">
            Proyecto urbanístico
          </span>
          <span className={`rounded-full px-3 py-0.5 text-xs font-semibold ${status.className}`}>
            {status.label}
          </span>
          {fase ? (
            <span className="rounded-full bg-sky-50 px-3 py-0.5 text-xs font-semibold text-sky-900 ring-1 ring-sky-200">
              {fase}
            </span>
          ) : null}
          {bocmCount > 0 ? (
            <span className="rounded-full bg-violet-50 px-3 py-0.5 text-xs font-semibold text-violet-900 ring-1 ring-violet-200">
              {bocmCount === 1 ? "1 anuncio en el Boletín" : `${bocmCount} anuncios en el Boletín`}
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

        {presentation.visorFicha ? (
          <SigmaVisorFichaHighlights ficha={presentation.visorFicha} />
        ) : null}

        <SigmaQueImplicaBlock presentation={{ ...presentation, bocmCount }} compact={compact} />

        <p
          className={`mt-3 max-w-3xl leading-relaxed text-slate-600 ${
            compact ? "line-clamp-3 text-xs" : "line-clamp-4 text-sm"
          }`}
        >
          {lead}
        </p>

        {meta ? (
          <p className={`text-slate-400 ${compact ? "mt-2 text-[11px]" : "mt-4 text-xs"}`}>
            {meta}
          </p>
        ) : null}

        <div className={`flex flex-wrap gap-2 ${compact ? "mt-3" : "mt-6"}`}>
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
