import Link from "next/link";
import type { LandingNewsFile } from "@/lib/landing-news";
import type { DataSummary } from "@/lib/types";

function formatGeneratedAt(iso: string): string {
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

export function LandingNewsSection({
  summary,
  news,
}: {
  summary: DataSummary | null;
  news: LandingNewsFile;
}) {
  const featured = news.items.find((x) => x.featured) ?? news.items[0];
  const rest = news.items.filter((x) => x !== featured);
  const updated = formatGeneratedAt(news.generatedAt);

  return (
    <section
      className="relative mt-8 overflow-hidden rounded-3xl border border-[#2d3640]/85 bg-[#3e4b5a] text-slate-100 shadow-[0_24px_80px_-20px_rgba(15,118,110,0.28)]"
      aria-labelledby="landing-news-heading"
    >
      <div
        className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-teal-500/20 blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -bottom-32 -left-16 h-72 w-72 rounded-full bg-cyan-400/12 blur-3xl"
        aria-hidden
      />

      <div className="relative px-5 py-10 sm:px-8 sm:py-12">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-teal-300/25 bg-teal-400/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.2em] text-teal-100/95">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-300/80 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-teal-200" />
              </span>
              Mayores actuaciones · Madrid
            </p>
            <h2
              id="landing-news-heading"
              className="mt-4 max-w-2xl text-3xl font-semibold tracking-tight text-white [text-wrap:balance] sm:text-4xl"
            >
              Noticias del territorio
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-slate-300/95 sm:text-base">
              Titulares automáticos a partir de los expedientes con más viviendas previstas en la
              documentación analizada. Se actualizan al regenerar los datos.
              {updated ? ` Última actualización: ${updated}.` : null}
            </p>
            {summary?.total ? (
              <p className="mt-4 max-w-xl border-l-2 border-teal-400/50 pl-4 text-sm text-teal-50/90">
                {news.items.length} macroactuaciones destacadas entre{" "}
                {summary.total.toLocaleString("es-ES")} anuncios indexados en el territorio.
              </p>
            ) : null}
          </div>
          <Link
            href="/explore"
            className="shrink-0 self-start rounded-xl border border-white/12 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white backdrop-blur-sm transition hover:border-teal-300/40 hover:bg-teal-500/15 lg:self-auto"
          >
            Ver en el mapa →
          </Link>
        </div>

        {featured ? (
          <Link
            href={featured.href}
            className="group relative mt-10 block overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.1] to-white/[0.02] p-6 transition hover:border-teal-300/35 sm:p-8"
          >
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wider text-teal-100/90">
              <span className="rounded-md bg-teal-400/15 px-2 py-0.5 text-teal-50">{featured.tag}</span>
              {featured.numViviendas != null ? (
                <>
                  <span className="text-slate-500">·</span>
                  <span className="tabular-nums text-teal-100">
                    {featured.numViviendas.toLocaleString("es-ES")} viviendas
                  </span>
                </>
              ) : null}
              <span className="text-slate-500">·</span>
              <time className="text-slate-400">{featured.dateLabel}</time>
            </div>
            <h3 className="mt-4 max-w-3xl text-xl font-semibold leading-snug tracking-tight text-white transition group-hover:text-teal-50 sm:text-2xl">
              {featured.title}
            </h3>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300/95 sm:text-base">{featured.dek}</p>
            <span className="mt-6 inline-flex items-center gap-1 text-sm font-semibold text-teal-200/95 transition group-hover:gap-2">
              Ver expediente
              <span aria-hidden>→</span>
            </span>
          </Link>
        ) : null}

        {rest.length > 0 ? (
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {rest.map((item) => (
              <li key={item.id}>
                <Link
                  href={item.href}
                  className="group flex h-full flex-col rounded-2xl border border-white/8 bg-[#323c48]/90 p-5 transition hover:-translate-y-0.5 hover:border-teal-300/30"
                >
                  <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
                    <span className="text-teal-200/90">{item.tag}</span>
                    {item.numViviendas != null ? (
                      <>
                        <span className="text-slate-600">·</span>
                        <span className="tabular-nums text-slate-400">
                          {item.numViviendas.toLocaleString("es-ES")} viv.
                        </span>
                      </>
                    ) : null}
                    <span className="text-slate-600">·</span>
                    <time className="text-slate-400">{item.dateLabel}</time>
                  </div>
                  <h3 className="mt-3 flex-1 text-base font-semibold leading-snug tracking-tight text-white transition group-hover:text-teal-50">
                    {item.title}
                  </h3>
                  <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-400">{item.dek}</p>
                  <span className="mt-4 text-xs font-semibold text-teal-300/90 group-hover:text-teal-200">
                    Ver ficha →
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}

        <p className="mt-6 text-center text-[11px] text-slate-500">
          Criterio: expedientes SIGMA con cifra de viviendas en documentación PDF · No es previsión
          oficial de obra terminada
        </p>
      </div>
    </section>
  );
}
