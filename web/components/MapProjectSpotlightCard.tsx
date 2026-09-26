"use client";

import Link from "next/link";
import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";
import type { MapProjectSpotlightItem } from "@/lib/map-project-spotlight";
import { PORTAL_TAG_TONE } from "@/lib/portal-tones";
import { sigmaClassificationTone } from "@/lib/sigma-classification";
import type { MapSpotlightPlacement } from "@/lib/map-spotlight-placement";
import { MAP_SPOTLIGHT_PLACEMENT_CLASS } from "@/lib/map-spotlight-placement";

function spotlightTitleParts(locationLine: string | null): {
  distrito: string | null;
  headline: string | null;
} {
  if (!locationLine) return { distrito: null, headline: null };
  const parts = locationLine.split(" · ").map((p) => p.trim()).filter(Boolean);
  if (parts.length >= 2) {
    return { distrito: parts[0] ?? null, headline: parts.slice(1).join(" · ") };
  }
  return { distrito: null, headline: locationLine };
}

function CardBody({ item }: { item: MapProjectSpotlightItem }) {
  const tone = sigmaClassificationTone(item.categoriaProyecto ?? item.tipoObra);
  const tagClass = PORTAL_TAG_TONE[tone];
  const { distrito, headline } = spotlightTitleParts(item.locationLine);

  return (
    <>
      <div className="flex items-start gap-3">
        <SigmaClassificationIcon
          clasificacion={{
            categoriaProyecto: item.categoriaProyecto,
            tipoObra: item.tipoObra,
          }}
          size="sm"
        />
        <div className="min-w-0 flex-1">
          <span
            className={`inline-flex max-w-full rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ring-1 ${tagClass}`}
          >
            <span className="truncate">{item.categoryLabel}</span>
          </span>
        </div>
      </div>
      {headline ? (
        <div className="mt-2.5">
          {distrito ? (
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
              {distrito}
            </p>
          ) : null}
          <h3
            className={`font-semibold leading-snug tracking-tight text-slate-900 ${
              distrito ? "mt-1" : ""
            } text-[15px] sm:text-base`}
          >
            {headline}
          </h3>
        </div>
      ) : null}
      <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-slate-600">{item.resumen}</p>
    </>
  );
}

export function MapProjectSpotlightCard({
  item,
  visible,
  variant = "landing",
  placement = "bottom-left",
  onClose,
  className = "",
}: {
  item: MapProjectSpotlightItem | null;
  visible: boolean;
  /** `landing`: sin interacción (el mapa enlaza a /explore). `explore`: enlace a ficha + cerrar. */
  variant?: "landing" | "explore";
  /** Esquina del mapa donde anclar la tarjeta (tour de inicio). */
  placement?: MapSpotlightPlacement;
  onClose?: () => void;
  className?: string;
}) {
  const show = visible && item != null;
  const interactive = variant === "explore";
  const linked = Boolean(item?.href);

  const placementStyle =
    variant === "explore"
      ? MAP_SPOTLIGHT_PLACEMENT_CLASS["bottom-right"]
      : MAP_SPOTLIGHT_PLACEMENT_CLASS[placement];

  return (
    <div
      className={`map-project-spotlight-card absolute z-[2100] w-[min(calc(100%-1.5rem),20.5rem)] transition-all duration-500 ease-out sm:w-[min(calc(100%-2rem),22rem)] ${placementStyle.position} ${
        linked ? "pointer-events-auto" : "pointer-events-none"
      } ${show ? placementStyle.visible : placementStyle.hidden} ${className}`}
      aria-hidden={!show}
    >
      {item ? (
        <article className="relative rounded-xl border border-[var(--portal-paper)]/95 bg-[var(--portal-paper)]/94 px-3.5 py-3 shadow-lg shadow-[var(--portal-ink)]/10 backdrop-blur-sm sm:px-4 sm:py-3.5">
          {interactive && onClose ? (
            <button
              type="button"
              onClick={onClose}
              className="absolute right-2 top-2 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="Cerrar"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                <path
                  d="M4 4l8 8M12 4L4 12"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          ) : null}
          {linked ? (
            <Link
              href={item.href}
              className={`block transition hover:opacity-95 ${interactive ? "pr-6" : ""}`}
            >
              <CardBody item={item} />
              <span className="mt-2.5 inline-flex text-xs font-semibold text-[var(--portal-accent)]">
                Ver ficha →
              </span>
            </Link>
          ) : (
            <CardBody item={item} />
          )}
        </article>
      ) : null}
    </div>
  );
}

/** @deprecated Usar MapProjectSpotlightCard */
export const LandingMapSpotlightCard = MapProjectSpotlightCard;
