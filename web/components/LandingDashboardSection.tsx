import Link from "next/link";
import { DASHBOARD } from "@/lib/ui-labels";

type TopDistrito = { name: string; count: number };

type LandingDashboardSectionProps = {
  planesCount?: number;
  licenciasCount?: number;
  latestLicenciasYear?: number;
  latestLicenciasTotal?: number;
  topDistritos?: TopDistrito[];
};

export function LandingDashboardSection({
  planesCount,
  licenciasCount,
  latestLicenciasYear,
  latestLicenciasTotal,
  topDistritos = [],
}: LandingDashboardSectionProps) {
  const statsLine =
    planesCount != null && licenciasCount != null
      ? `${planesCount.toLocaleString("es-ES")} planes indexados · ${licenciasCount.toLocaleString("es-ES")} licencias de obra`
      : null;

  const maxDistrito = topDistritos[0]?.count ?? 1;

  return (
    <section
      className="border-y border-slate-200/80 bg-slate-900 px-4 py-12 text-white sm:px-6 sm:py-14"
      aria-labelledby="landing-dashboard-heading"
    >
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)] lg:items-center lg:gap-12">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300/90">
              Para equipos y análisis
            </p>
            <h2
              id="landing-dashboard-heading"
              className="mt-3 text-3xl font-semibold tracking-tight [text-wrap:balance] sm:text-4xl"
            >
              {DASHBOARD} de actividad urbanística
            </h2>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-slate-300">
              Licencias por distrito, evolución anual, rankings de promotores y cruce con
              planeamiento. Datos agregados del Ayuntamiento de Madrid capital, listos para
              comparar y exportar.
            </p>
            {statsLine ? (
              <p className="mt-4 text-sm text-slate-400">{statsLine}</p>
            ) : null}
            <Link
              href="/madrid/estadisticas"
              className="mt-8 inline-flex items-center justify-center rounded-xl bg-white px-6 py-3.5 text-sm font-semibold text-slate-900 shadow-lg transition hover:bg-slate-100"
            >
              Abrir {DASHBOARD.toLowerCase()} →
            </Link>
          </div>

          {latestLicenciasTotal != null || topDistritos.length > 0 ? (
            <div
              className="rounded-2xl border border-white/10 bg-white/5 p-6 ring-1 ring-white/10 sm:p-8"
              aria-hidden
            >
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-teal-300/80">
                Vista previa
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                {latestLicenciasTotal != null && latestLicenciasYear != null ? (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <p className="text-2xl font-semibold tabular-nums">
                      {latestLicenciasTotal.toLocaleString("es-ES")}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      Licencias · {latestLicenciasYear}
                    </p>
                  </div>
                ) : null}
                {planesCount != null ? (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <p className="text-2xl font-semibold tabular-nums">
                      {planesCount.toLocaleString("es-ES")}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">Planes en mapa</p>
                  </div>
                ) : null}
              </div>
              {topDistritos.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {topDistritos.map((d, i) => (
                    <div key={d.name} className="flex items-center gap-3 text-sm">
                      <span className="w-4 shrink-0 text-slate-500 tabular-nums">{i + 1}.</span>
                      <span className="min-w-0 flex-1 truncate text-slate-200">{d.name}</span>
                      <span
                        className="h-2 max-w-[40%] shrink-0 rounded-full bg-teal-400/80"
                        style={{ width: `${Math.max(12, (d.count / maxDistrito) * 40)}%` }}
                      />
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
