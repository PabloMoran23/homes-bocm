import Link from "next/link";
import { LandingAddressForm } from "@/components/LandingAddressForm";
import { LandingDashboardSection } from "@/components/LandingDashboardSection";
import { LandingMap } from "@/components/LandingMap";
import { LandingNewsSection } from "@/components/LandingNewsSection";
import { LandingTuZonaSection } from "@/components/LandingTuZonaSection";
import { isPublicEdition } from "@/lib/edition";
import { loadLandingNews } from "@/lib/landing-news";
import { loadMadridDashboardStats } from "@/lib/load-madrid-dashboard";
import { loadSummary } from "@/lib/load-summary";
import { DASHBOARD } from "@/lib/ui-labels";

function formatUpdatedAt(iso: string | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("es-ES", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

function titleCaseDistrito(name: string): string {
  const lower = name.toLowerCase().replace(/_/g, " ");
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export default async function Home() {
  const summary = await loadSummary();
  const news = loadLandingNews();
  const dashboardStats = await loadMadridDashboardStats();
  const isPublic = isPublicEdition();

  const planesCount = dashboardStats?.sigma?.total;
  const licenciasCount = dashboardStats?.licencias?.totalRows;
  const updatedAt = formatUpdatedAt(news.generatedAt ?? summary?.generatedAt);
  const latestLicenciasYear = dashboardStats?.licencias?.seriesByYear?.at(-1);
  const topDistritos = dashboardStats?.licencias?.topDistrito?.slice(0, 3) ?? [];

  return (
    <main className="flex-1">
      <section className="portal-hero-bg border-b border-slate-200/80 px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:items-start lg:gap-12 xl:gap-14">
            <div className="min-w-0">
              {isPublic ? (
                <p className="text-sm font-medium uppercase tracking-wider text-[var(--portal-warm)]">
                  Lo que pasa en Madrid capital
                </p>
              ) : (
                <p className="text-sm font-medium uppercase tracking-wider text-[var(--portal-warm)]">
                  La ciudad que viene, antes que nadie
                </p>
              )}
              <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight text-[var(--portal-ink)] sm:text-5xl">
                Qué se está moviendo{" "}
                <span className="text-[var(--portal-accent)]">cerca de ti</span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">
                {isPublic ? (
                  <>
                    Obras, planes y anuncios oficiales en un solo sitio. Escribe tu calle y mira qué
                    ha pasado alrededor — o explora toda la ciudad.
                  </>
                ) : (
                  <>
                    Obras, planes y anuncios oficiales en un solo sitio. Sigue lo que cambia cerca
                    de ti, configura alertas y entiende el pulso del suelo en minutos.
                  </>
                )}
              </p>

              {planesCount || licenciasCount || updatedAt ? (
                <p className="mt-4 text-sm text-slate-500">
                  {planesCount ? (
                    <>
                      <span className="font-semibold text-slate-700">
                        {planesCount.toLocaleString("es-ES")} planes
                      </span>
                      {" en mapa"}
                    </>
                  ) : null}
                  {planesCount && licenciasCount ? " · " : null}
                  {licenciasCount ? (
                    <>
                      <span className="font-semibold text-slate-700">
                        {licenciasCount.toLocaleString("es-ES")} obras indexadas
                      </span>
                    </>
                  ) : null}
                  {updatedAt ? (
                    <>
                      {" · "}
                      <span>Actualizado el {updatedAt}</span>
                    </>
                  ) : null}
                </p>
              ) : null}

              <LandingAddressForm variant="hero" showSecondaryLink={false} />

              <p className="mt-4 text-sm text-slate-600">
                o{" "}
                <Link
                  href="/explore"
                  className="font-semibold text-[var(--portal-accent)] hover:underline"
                >
                  abrir mapa
                </Link>
                {" · "}
                <Link
                  href="/madrid/estadisticas"
                  className="font-semibold text-[var(--portal-accent)] hover:underline"
                >
                  {DASHBOARD.toLowerCase()}
                </Link>
              </p>
            </div>
            <div className="min-w-0 lg:pt-1">
              <LandingMap />
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pt-10 pb-4 sm:px-6 sm:pt-12">
        <LandingNewsSection summary={summary} news={news} />
      </section>

      <LandingTuZonaSection isPublic={isPublic} />

      <LandingDashboardSection
        planesCount={planesCount}
        licenciasCount={licenciasCount}
        latestLicenciasYear={latestLicenciasYear?.year}
        latestLicenciasTotal={latestLicenciasYear?.total}
        topDistritos={topDistritos.map((d) => ({
          name: titleCaseDistrito(d.name),
          count: d.count,
        }))}
      />

      <section className="mx-auto max-w-6xl px-4 pb-10 sm:px-6 sm:pb-12">
        <div className="grid gap-8 border-t border-slate-200 pt-14 sm:grid-cols-3">
          <div>
            <h3 className="font-semibold text-slate-900">Vives o estás mirando un piso</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              Anticiparte a obras y cambios en el barrio antes de que salgan en las noticias. Ideal
              si compras, alquilas o quieres saber qué pasa en tu calle.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Trabajas con suelo o inversión</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              Compara barrios, evolución en el tiempo y casos concretos desde el{" "}
              {DASHBOARD.toLowerCase()}. Licencias, planeamiento y métricas agregadas.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">
              {isPublic ? "Más por venir" : "Si escalas un equipo"}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {isPublic ? (
                <>
                  Alertas por correo y planes de suscripción en el roadmap.{" "}
                  <Link
                    href="/en-desarrollo?from=/planes"
                    className="font-medium text-[var(--portal-accent)] hover:underline"
                  >
                    Ver qué viene
                  </Link>
                </>
              ) : (
                <>
                  Misma inteligencia para varias zonas: alertas compartidas, API e integraciones en
                  roadmap — todo sobre el mismo núcleo de datos.
                </>
              )}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
