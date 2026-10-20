import nextDynamic from "next/dynamic";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AnalyticsBody, RankList, ReadingNotes, RecentSessions } from "@/components/admin/analytics/AnalyticsBody";
import { AnalyticsFilters } from "@/components/admin/analytics/AnalyticsFilters";
import { LogoutButton } from "@/components/admin/analytics/LogoutButton";
import { ADMIN_COOKIE, isValidAdminSession } from "@/lib/admin-auth";
import { getAnalyticsDashboard, toDashboardView, type DashboardView } from "@/lib/analytics-dashboard";
import {
  analyticsHref,
  parseAnalyticsQuery,
  rangeLabel,
  requestedAnalyticsHref,
  type AnalyticsSearch,
} from "@/lib/analytics-filters";
import { isPublicEdition } from "@/lib/edition";

const AnalyticsCharts = nextDynamic(
  () => import("@/components/admin/analytics/AnalyticsCharts").then((mod) => mod.AnalyticsCharts),
  {
    loading: () => <div className="h-72 animate-pulse rounded-2xl bg-white/70" />,
  },
);

export const dynamic = "force-dynamic";
export const metadata = {
  title: { absolute: "Analítica · Homes" },
  robots: { index: false, follow: false },
};

type SearchParams = Record<string, string | string[] | undefined>;

export default async function AnalyticsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const raw = await searchParams;
  const preview = process.env.NODE_ENV === "development" && first(raw.muestra) === "1";
  const search = toSearch(raw);
  const query = parseAnalyticsQuery(search);
  if (!preview && requestedAnalyticsHref(search) !== analyticsHref(query)) {
    redirect(analyticsHref(query));
  }
  if (!preview && !(await isValidAdminSession((await cookies()).get(ADMIN_COOKIE)?.value))) {
    redirect("/admin/login?from=/admin/analitica");
  }

  let view: DashboardView | null = null;
  let error: string | null = null;
  if (preview) {
    const { sampleReport } = await import("@/lib/analytics-sample");
    view = toDashboardView(sampleReport(query), query, true);
  } else {
    try {
      view = toDashboardView(await getAnalyticsDashboard(query), query);
    } catch (caught) {
      error = caught instanceof Error ? caught.message : "No se ha podido consultar la analítica.";
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--portal-accent)]">Interno</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">Analítica</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            {rangeLabel(query.range)} · {query.currentLabel}. Comparado con {query.previousLabel}, misma duración.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isPublicEdition() ? null : (
            <a href="/admin" className="rounded-full px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-white">
              Operaciones
            </a>
          )}
          <LogoutButton />
        </div>
      </header>
      {preview ? (
        <p className="mb-4 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          Datos de ejemplo, no son visitas reales. Sirven para ver el panel sin la base de datos.
        </p>
      ) : null}
      <div className="mb-4">
        <AnalyticsFilters value={query} preview={preview} />
      </div>
      {error ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-900">{error}</p>
      ) : view ? (
        <div className="space-y-4">
          <AnalyticsBody view={view} />
          <AnalyticsCharts charts={view.charts} />
          <div className="grid gap-4 lg:grid-cols-2">
            <RankList title="Páginas" subtitle="Cualquier ruta, ordenada por vistas." rows={view.pages} empty="Sin páginas para este filtro." />
            <RankList title="Proyectos" subtitle="Fichas en /proyecto." rows={view.projects} empty="Sin fichas de proyecto para este filtro." />
            <RankList title="Lugares" subtitle={view.placesNote} rows={view.places} empty="Sin directorio ni fichas de ubicación para este filtro." />
            <RankList title="Páginas de entrada" subtitle="Primera página de cada sesión." rows={view.entries} empty="Sin entradas para este filtro." />
            <RankList title="Origen" subtitle="De dónde llega la sesión." rows={view.sources} empty="Sin orígenes para este filtro." />
            <RankList title="Secciones" subtitle="Agrupación de rutas." rows={view.sections} empty="Sin secciones para este filtro." />
            <RankList title="Acciones" subtitle="Lo que ocurre además de ver la página." rows={view.actions} empty="Sin acciones para este filtro." />
          </div>
          <RecentSessions rows={view.recent} />
          <ReadingNotes />
        </div>
      ) : null}
    </div>
  );
}

function toSearch(raw: SearchParams): AnalyticsSearch {
  return {
    r: first(raw.r),
    from: first(raw.from),
    to: first(raw.to),
    traffic: first(raw.traffic),
    source: first(raw.source),
    section: first(raw.section),
    days: first(raw.days),
  };
}

function first(value: string | string[] | undefined): string | undefined {
  const picked = Array.isArray(value) ? value[0] : value;
  return picked || undefined;
}
