import Link from "next/link";
import type { LandingNewsFile, LandingNewsSpotlight } from "@/lib/landing-news";
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

function RadarBadge() {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-teal-200/90 bg-[var(--portal-accent-soft)]/60 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-teal-900">
      <span className="relative flex h-2 w-2" aria-hidden>
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--portal-accent)] opacity-70" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--portal-accent)]" />
      </span>
      Radar activo · Madrid
    </span>
  );
}

function MetaLine({ item }: { item: LandingNewsSpotlight }) {
  const parts: string[] = [item.dateLabel];
  if (item.valueLabel) parts.push(item.valueLabel);
  if (item.numViviendas != null) {
    parts.push(`${item.numViviendas.toLocaleString("es-ES")} viviendas`);
  }
  return (
    <p className="mt-3 text-xs text-slate-500">
      {parts.join(" · ")}
    </p>
  );
}

function FeaturedCase({ item }: { item: LandingNewsSpotlight }) {
  return (
    <article className="min-w-0">
      <Link
        href={item.href}
        className="group block rounded-2xl border border-teal-100/90 bg-gradient-to-br from-teal-50/70 via-white to-white p-6 ring-1 ring-teal-900/[0.04] transition hover:border-teal-200/90 hover:shadow-md hover:shadow-teal-900/5 sm:p-8"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-[var(--portal-accent)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
            Destacado
          </span>
          <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--portal-accent)]">
            {item.tag}
          </span>
        </div>
        <h3 className="mt-4 text-xl font-semibold leading-snug tracking-tight text-slate-900 transition group-hover:text-[var(--portal-accent)] sm:text-2xl">
          {item.title}
        </h3>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
          {item.dek}
        </p>
        {item.trendLabel ? (
          <p className="mt-3 inline-flex rounded-lg border border-teal-200/80 bg-teal-50/80 px-3 py-1.5 text-xs font-medium text-teal-900">
            {item.trendLabel}
          </p>
        ) : null}
        <MetaLine item={item} />
        <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[var(--portal-accent)] transition group-hover:gap-2">
          {item.ctaLabel ?? "Ver caso"}
          <span aria-hidden>→</span>
        </span>
      </Link>
    </article>
  );
}

function BriefCase({ item }: { item: LandingNewsSpotlight }) {
  return (
    <article className="min-w-0">
      <Link
        href={item.href}
        className="group flex h-full flex-col rounded-xl border border-slate-200/90 bg-white p-5 transition hover:border-teal-200/90 hover:shadow-sm hover:shadow-teal-900/5"
      >
        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--portal-accent)]">
          {item.tag}
        </span>
        <h3 className="mt-2 flex-1 text-base font-semibold leading-snug text-slate-900 transition group-hover:text-[var(--portal-accent)]">
          {item.title}
        </h3>
        <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-slate-600">{item.dek}</p>
        {item.trendLabel ? (
          <p className="mt-2 text-[11px] font-medium text-teal-800/90">{item.trendLabel}</p>
        ) : null}
        <MetaLine item={item} />
        <span className="mt-3 text-xs font-semibold text-[var(--portal-accent)]">
          {item.ctaLabel ?? "Abrir ficha"} →
        </span>
      </Link>
    </article>
  );
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
      className="relative mt-10 overflow-hidden rounded-2xl border border-teal-100/90 bg-white shadow-sm ring-1 ring-slate-900/[0.03]"
      aria-labelledby="landing-news-heading"
    >
      <div
        className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-teal-400/10 blur-3xl"
        aria-hidden
      />

      <div className="relative px-5 py-8 sm:px-8 sm:py-10">
        <header className="flex flex-col gap-5 border-b border-teal-100/80 pb-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <RadarBadge />
            <h2
              id="landing-news-heading"
              className="mt-4 text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl"
            >
              En el radar{" "}
              <span className="text-[var(--portal-accent)]">urbanístico</span>
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
              Cada día cruzamos licencias y planeamiento de Madrid capital y sacamos a la superficie
              los expedientes que más destacan: obra reciente, cambios de uso, densidad o superficie
              llamativa.
              {updated ? (
                <span className="text-slate-500"> Actualizado el {updated}.</span>
              ) : null}
            </p>
            {summary?.total ? (
              <p className="mt-3 text-xs text-slate-500">
                <span className="font-semibold text-teal-800">{news.items.length} casos</span> en
                esta selección · analizamos{" "}
                {summary.total.toLocaleString("es-ES")} registros y anuncios de referencia
              </p>
            ) : null}
          </div>
          <Link
            href="/explore"
            className="shrink-0 self-start rounded-lg border border-teal-200/80 bg-teal-50/50 px-4 py-2.5 text-sm font-semibold text-[var(--portal-accent)] transition hover:bg-[var(--portal-accent-soft)]"
          >
            Ver en el mapa →
          </Link>
        </header>

        {featured ? (
          <div className="mt-8">
            <FeaturedCase item={featured} />
          </div>
        ) : null}

        {rest.length > 0 ? (
          <div className="mt-8">
            <p className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <span className="h-px flex-1 max-w-[2rem] bg-teal-300/80" aria-hidden />
              Más en el radar
              <span className="h-px flex-1 bg-teal-100" aria-hidden />
            </p>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {rest.map((item) => (
                <li key={item.id}>
                  <BriefCase item={item} />
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <footer className="mt-8 border-t border-teal-50 pt-4 text-[11px] leading-relaxed text-slate-500">
          Detección a partir de datos abiertos del Ayuntamiento. No es previsión oficial de obra
          terminada.
        </footer>
      </div>
    </section>
  );
}
