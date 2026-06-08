"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSigmaAmbitosLandingGeo } from "@/lib/madrid-sigma-map";
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

export function LandingMap() {
  const { ref, visible } = useInViewport();
  const { geo, err, ready, loading } = useSigmaAmbitosLandingGeo(visible);

  if (err) {
    return (
      <div className="rounded-2xl border border-amber-200/90 bg-amber-50/90 px-4 py-6 text-center text-sm text-amber-950">
        <p>{err}</p>
        <p className="mt-2 text-xs text-amber-800/90">
          En la carpeta <code className="rounded bg-amber-100/80 px-1 font-mono">web/</code> ejecuta{" "}
          <code className="rounded bg-amber-100/80 px-1 font-mono">npm run build-data</code>.
        </p>
      </div>
    );
  }

  return (
    <div ref={ref} className="flex flex-col gap-2">
      <div
        className={`landing-map-live group relative overflow-hidden rounded-2xl ring-1 ring-slate-200/90 transition hover:ring-[var(--portal-accent)]/40 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--portal-accent)] ${MAP_HEIGHT}`}
      >
        {!visible || !ready || !geo?.features?.length ? (
          <LandingMapPlaceholder hint={loading ? "Cargando mapa…" : undefined} />
        ) : (
          <MadridUnifiedMap
            ubicacionesGeojson={null}
            sigmaGeojson={geo}
            highlightNdp={null}
            onSelectNdp={() => {}}
            showUbicaciones={false}
            showSigma
            interactive={false}
            fitToData={false}
            initialView="preview"
            landingPulse
            statsHint="Actividad reciente en Madrid"
            className="h-full w-full rounded-2xl"
            showAttribution={false}
          />
        )}

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
