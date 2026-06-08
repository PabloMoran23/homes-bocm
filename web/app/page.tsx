import Link from "next/link";
import { LandingMap } from "@/components/LandingMap";
import { LandingNewsSection } from "@/components/LandingNewsSection";
import { LandingTuZonaSection } from "@/components/LandingTuZonaSection";
import { loadLandingNews } from "@/lib/landing-news";
import { loadSummary } from "@/lib/load-summary";
import { isPublicEdition } from "@/lib/edition";

export default async function Home() {
  const summary = await loadSummary();
  const news = loadLandingNews();
  const isPublic = isPublicEdition();

  return (
    <main className="flex-1">
      <section className="portal-hero-bg border-b border-slate-200/80 px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:items-start lg:gap-12 xl:gap-14">
            <div className="min-w-0">
              {isPublic ? (
                <p className="text-sm font-medium uppercase tracking-wider text-[var(--portal-warm)]">
                  Madrid capital
                </p>
              ) : (
                <p className="text-sm font-medium uppercase tracking-wider text-[var(--portal-warm)]">
                  La ciudad que viene, antes que nadie
                </p>
              )}
              <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight text-[var(--portal-ink)] sm:text-5xl">
                Proyectos urbanísticos{" "}
                <span className="text-[var(--portal-accent)]">en tu zona</span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">
                {isPublic ? (
                  <>
                    Homes concentra en un solo mapa lo que ocurre en Madrid capital: licencias de
                    obra, proyectos de planeamiento y anuncios del BOCM enlazados. Introduce tu dirección en
                    el boletín, explora el territorio y consulta estadísticas agregadas.
                  </>
                ) : (
                  <>
                    Homes centraliza lo que cambia el tejido alrededor de ti: qué se tramita, dónde y
                    con qué intensidad. Sigue proyectos, configura alertas, estudia un ámbito y
                    entiende el pulso del suelo en minutos.
                  </>
                )}
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/boletin"
                  className="inline-flex items-center justify-center rounded-lg bg-[var(--portal-accent)] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--portal-accent-hover)]"
                >
                  Qué ocurre en tu zona
                </Link>
                <Link
                  href="/explore"
                  className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 shadow-sm transition hover:bg-slate-50"
                >
                  Explorar Madrid
                </Link>
                <Link
                  href="/madrid/estadisticas"
                  className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 shadow-sm transition hover:bg-slate-50"
                >
                  Ver estadísticas
                </Link>
              </div>
            </div>
            <div className="min-w-0 lg:pt-1">
              <LandingMap />
            </div>
          </div>
        </div>
      </section>

      <LandingTuZonaSection isPublic={isPublic} />

      <section className="mx-auto max-w-6xl px-4 pt-5 pb-10 sm:px-6 sm:pt-6 sm:pb-12">
        <LandingNewsSection summary={summary} news={news} />

        <div className="mt-14 grid gap-8 border-t border-slate-200 pt-14 sm:grid-cols-3">
          <div>
            <h3 className="font-semibold text-slate-900">Si vives o compras ahí</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              Entiende qué se cuece en tu barrio antes de que sea noticia. Ideal para anticiparte a
              obras, cambios de usos o nuevas dotaciones.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">Si analizas suelo</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              Cruza licencias, planeamiento y anuncios en segundos; compara distritos y evolución
              temporal desde el panel de estadísticas.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">
              {isPublic ? "Próximamente" : "Si escalas un equipo"}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {isPublic ? (
                <>
                  Alertas por correo y planes de suscripción llegarán en próximas versiones.{" "}
                  <Link href="/en-desarrollo?from=/planes" className="font-medium text-[var(--portal-accent)] hover:underline">
                    Ver roadmap
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
