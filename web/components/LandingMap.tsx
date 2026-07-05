"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useState } from "react";
import { MapProjectSpotlightCard } from "@/components/MapProjectSpotlightCard";
import type { LandingMapSpotlightFile, LandingMapSpotlightItem } from "@/lib/landing-map-spotlight";
import type { LandingTourActiveChange } from "@/lib/landing-map-tour";
import type { MapSpotlightPlacement } from "@/lib/map-spotlight-placement";
import { useSigmaAmbitosLandingGeo } from "@/lib/madrid-sigma-map";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import { useInViewport } from "@/lib/use-in-viewport";

const MadridUnifiedMap = dynamic(
  () => import("./MadridUnifiedMap").then((m) => ({ default: m.MadridUnifiedMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[320px] h-[min(42vh,480px)] items-center justify-center rounded-2xl border border-dashed border-slate-200/90 bg-white/60 text-sm text-slate-500 shadow-inner lg:h-[min(52vh,560px)]">
        Cargando mapa…
      </div>
    ),
  },
);

const MAP_HEIGHT =
  "min-h-[280px] h-[min(40vh,440px)] sm:min-h-[320px] sm:h-[min(44vh,500px)] lg:min-h-[360px] lg:h-[min(52vh,580px)]";

function LandingMapPlaceholder({ hint }: { hint?: string }) {
  return (
    <div
      className={`flex items-center justify-center rounded-2xl border border-dashed border-slate-200/90 bg-gradient-to-br from-teal-50/80 to-white/90 text-sm text-slate-500 shadow-inner ${MAP_HEIGHT}`}
      aria-hidden
    >
      {hint ?? "Cargando mapa…"}
    </div>
  );
}

type LandingMapProps = {
  /** Precargado en servidor; evita un fetch extra en cliente que puede fallar en producción. */
  sigmaGeojson?: SectorFeatureCollection | null;
  spotlight?: LandingMapSpotlightFile | null;
  tourGeojson?: SectorFeatureCollection | null;
};

export function LandingMap({ sigmaGeojson, spotlight, tourGeojson }: LandingMapProps) {
  const hasServerGeo = Boolean(sigmaGeojson?.features?.length);
  const hasTour = Boolean(spotlight?.items?.length && tourGeojson?.features?.length);
  const { ref, visible } = useInViewport();
  const client = useSigmaAmbitosLandingGeo(!hasServerGeo && visible && !hasTour);
  const [activeSpotlight, setActiveSpotlight] = useState<LandingMapSpotlightItem | null>(null);
  const [cardPlacement, setCardPlacement] = useState<MapSpotlightPlacement>("bottom-left");

  const onTourActiveChange = useCallback(({ item, placement }: LandingTourActiveChange) => {
    setActiveSpotlight(item);
    if (placement) setCardPlacement(placement);
  }, []);

  const geo = hasServerGeo ? sigmaGeojson : client.geo;
  const err = hasServerGeo || hasTour ? null : client.err;
  const ready = hasServerGeo || hasTour || client.ready;
  const loading = !hasServerGeo && !hasTour && client.loading;

  if (err) {
    return (
      <div className="rounded-2xl border border-amber-200/90 bg-amber-50/90 px-4 py-6 text-center text-sm text-amber-950">
        <p>{err}</p>
        <p className="mt-2 text-xs text-amber-800/90">
          Prueba a recargar la página o{" "}
          <Link href="/explore" className="font-semibold underline underline-offset-2">
            abrir el mapa completo
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div ref={ref} className="flex flex-col gap-2">
      <div
        className={`landing-map-live group relative overflow-hidden rounded-2xl ring-1 ring-slate-200/90 transition hover:ring-[var(--portal-accent)]/40 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--portal-accent)] ${MAP_HEIGHT}`}
      >
        {!visible || !ready || (!hasTour && !geo?.features?.length) ? (
          <LandingMapPlaceholder hint={loading ? "Cargando mapa…" : undefined} />
        ) : (
          <MadridUnifiedMap
            ubicacionesGeojson={null}
            sigmaGeojson={geo ?? null}
            highlightNdp={null}
            onSelectNdp={() => {}}
            showUbicaciones={false}
            showSigma
            interactive={false}
            fitToData={false}
            initialView="preview"
            landingTour={hasTour}
            landingTourItems={spotlight?.items ?? []}
            tourGeojson={tourGeojson ?? null}
            onLandingTourActiveChange={onTourActiveChange}
            landingPulse={!hasTour}
            statsHint={hasTour ? null : "Actividad reciente en Madrid"}
            className="h-full w-full rounded-2xl"
            showAttribution={false}
          />
        )}

        {hasTour ? (
          <MapProjectSpotlightCard
            item={activeSpotlight}
            visible={activeSpotlight != null}
            variant="landing"
            placement={cardPlacement}
          />
        ) : null}

        <div className="landing-map-live-overlay pointer-events-none absolute inset-0 z-[1500]" aria-hidden>
          <div className="landing-map-live-badge">
            <span className="landing-map-live-dot" />
            En vivo
          </div>
        </div>

        <Link
          href="/explore"
          className="absolute inset-0 z-[2000] block cursor-pointer rounded-2xl"
          aria-label="Abrir mapa de Madrid"
        />
        <span className="pointer-events-none absolute bottom-3 right-3 z-[2001] rounded-full border border-white/90 bg-white/92 px-3 py-1.5 text-xs font-semibold text-[var(--portal-accent)] shadow-md opacity-0 transition group-hover:opacity-100">
          Abrir mapa →
        </span>
      </div>
    </div>
  );
}
