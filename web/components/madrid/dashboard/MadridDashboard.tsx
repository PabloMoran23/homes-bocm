"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { DonutChart } from "@/components/madrid/dashboard/DonutChart";

const DistritosCountMap = dynamic(
  () =>
    import("@/components/madrid/dashboard/DistritosCountMap").then((m) => m.DistritosCountMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[380px] animate-pulse items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-sm text-slate-400 md:col-span-2">
        Cargando mapa…
      </div>
    ),
  },
);
import { DashboardSection } from "@/components/madrid/dashboard/DashboardSection";
import { KpiCard } from "@/components/madrid/dashboard/KpiCard";
import { GranularityToggle } from "@/components/madrid/dashboard/GranularityToggle";
import { LicenciaMapaLineChart } from "@/components/madrid/dashboard/LicenciaMapaLineChart";
import { YearEvolutionChart } from "@/components/madrid/dashboard/YearEvolutionChart";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import type { LicenciasTimeGranularity, MadridDashboardStats } from "@/lib/types";

type Tab = "licencias" | "sigma";

function fmt(n: number) {
  return n.toLocaleString("es-ES");
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("es-ES", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function MadridDashboard({ stats }: { stats: MadridDashboardStats }) {
  const [tab, setTab] = useState<Tab>("licencias");
  const [licGranularity, setLicGranularity] = useState<LicenciasTimeGranularity>("year");
  const lic = stats.licencias;
  const sig = stats.sigma;

  return (
    <div className="min-h-full">
      {/* Hero */}
      <div className="border-b border-slate-200/80 bg-gradient-to-br from-[var(--portal-accent-soft)]/40 via-white to-slate-50">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--portal-accent)]">
            Ayuntamiento de Madrid
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Estadísticas urbanísticas
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
            Licencias urbanísticas (datos abiertos) y planeamiento SIGMA en un solo panel.
            Gráficos interactivos con filtro temporal.
          </p>
          <p className="mt-2 text-xs text-slate-400">
            Actualizado {fmtDate(stats.generatedAt)}
            {lic ? ` · Licencias ${fmtDate(lic.generatedAt)}` : ""}
          </p>

          <div className="mt-6 inline-flex rounded-xl border border-slate-200/90 bg-white/80 p-1 shadow-sm backdrop-blur-sm">
            <button
              type="button"
              onClick={() => setTab("licencias")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-all ${
                tab === "licencias"
                  ? "bg-[var(--portal-accent)] text-white shadow-md shadow-teal-900/15"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              Licencias
            </button>
            <button
              type="button"
              onClick={() => setTab("sigma")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-all ${
                tab === "sigma"
                  ? "bg-[var(--portal-accent)] text-white shadow-md shadow-teal-900/15"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              Planeamiento SIGMA
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="mb-6 flex justify-end">
          <Link
            href="/explore"
            className="inline-flex items-center gap-1 text-sm font-medium text-[var(--portal-accent)] hover:underline"
          >
            Ver mapa explorar
            <span aria-hidden>→</span>
          </Link>
        </div>

        {tab === "licencias" && lic ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard label="Licencias en dataset" value={fmt(lic.totalRows)} />
              <KpiCard
                label="Con ubicación"
                value={fmt(lic.withCoords)}
                hint={`${Math.round((lic.withCoords / lic.totalRows) * 100)} % geolocalizadas`}
                accent="sky"
              />
              <KpiCard
                label="Años cubiertos"
                value={`${lic.years[0]} – ${lic.years[lic.years.length - 1]}`}
              />
              <KpiCard
                label="Pico anual"
                value={fmt(Math.max(...lic.seriesByYear.map((s) => s.total)))}
                hint="Mayor volumen en un solo año"
                accent="amber"
              />
            </div>

            <DashboardSection
              title="Evolución temporal"
              description="Tendencia global y desglose por tipo de licencia (mismos iconos que en el mapa)."
            >
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-slate-500">
                  {licGranularity === "year"
                    ? "Vista anual del dataset."
                    : "Vista mensual según fecha de concesión."}
                </p>
                <GranularityToggle value={licGranularity} onChange={setLicGranularity} />
              </div>
              <div className="grid gap-5">
                <YearEvolutionChart
                  title="Licencias concedidas"
                  series={lic.seriesByYear.map((s) => ({ year: s.year, value: s.total }))}
                  seriesByMonth={lic.seriesByMonth}
                  granularity={licGranularity}
                  valueLabel="licencias"
                />
                {lic.seriesByYearMapaTipo?.length ? (
                  <LicenciaMapaLineChart
                    title="Por tipo de licencia"
                    seriesByYear={lic.seriesByYearMapaTipo}
                    seriesByMonth={lic.seriesByMonthMapaTipo}
                    granularity={licGranularity}
                  />
                ) : null}
              </div>
            </DashboardSection>

            <DashboardSection
              title="Distribución"
              description="Composición global del dataset; distritos en mapa según ubicación de las licencias."
            >
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                <DistritosCountMap
                  title="Distritos"
                  items={lic.topDistrito}
                  mapPoints={lic.topDistritoMap}
                  valueLabel="licencias"
                />
                <DonutChart title="Uso del suelo" items={lic.topUso} maxItems={8} valueLabel="licencias" />
                <DonutChart
                  title="Procedimiento"
                  items={lic.topProcedimiento}
                  maxItems={8}
                  valueLabel="licencias"
                />
                {lic.topTipoExpediente.length > 0 ? (
                  <DonutChart
                    title="Tipo de expediente (raw)"
                    items={lic.topTipoExpediente}
                    maxItems={7}
                    valueLabel="licencias"
                  />
                ) : null}
              </div>
            </DashboardSection>
          </>
        ) : null}

        {tab === "licencias" && !lic ? (
          <p className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
            Índice de licencias no disponible. Ejecuta{" "}
            <code className="rounded bg-amber-100/80 px-1.5 py-0.5 text-xs">npm run build-data</code>.
          </p>
        ) : null}

        {tab === "sigma" ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard label="Expedientes SIGMA" value={fmt(sig.total)} />
              <KpiCard
                label="Ficha visor"
                value={fmt(sig.conVisorFicha)}
                hint={`${Math.round((sig.conVisorFicha / sig.total) * 100)} % enriquecidos`}
                accent="sky"
              />
              <KpiCard
                label="Con tramitación"
                value={fmt(sig.conTramitacion)}
                hint="Historial en visor"
              />
              <KpiCard
                label="En mapa"
                value={fmt(sig.conGeometry)}
                hint="Con geometría"
                accent="amber"
              />
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard
                label="Métricas PDF"
                value={fmt(sig.conMetricasPdf)}
                hint="Viviendas y superficies"
              />
              <KpiCard
                label="Viviendas (PDF)"
                value={fmt(sig.viviendasEnMetricas)}
                hint={`${sig.expedientesConViviendas} expedientes`}
                accent="sky"
              />
              <KpiCard
                label="Iniciativa privada"
                value={
                  sig.byIniciativa.find((x) => x.name.toLowerCase().includes("privada"))?.count
                    ? fmt(
                        sig.byIniciativa.find((x) =>
                          x.name.toLowerCase().includes("privada"),
                        )!.count,
                      )
                    : "—"
                }
              />
              <KpiCard
                label="Iniciativa municipal"
                value={
                  sig.byIniciativa.find((x) => x.name.toLowerCase().includes("municipal"))?.count
                    ? fmt(
                        sig.byIniciativa.find((x) =>
                          x.name.toLowerCase().includes("municipal"),
                        )!.count,
                      )
                    : "—"
                }
                accent="amber"
              />
            </div>

            <DashboardSection title="Evolución temporal">
              <div className="grid gap-5 lg:grid-cols-2">
                <YearEvolutionChart
                  title="Expedientes por año de apertura"
                  series={sig.seriesByYear.map((s) => ({ year: s.year, value: s.count }))}
                  valueLabel="expedientes"
                  color="#0e7490"
                />
                <DonutChart
                  title="Superficie del ámbito"
                  items={sig.superficieBuckets}
                  maxItems={4}
                  valueLabel="expedientes"
                />
              </div>
            </DashboardSection>

            <DashboardSection title="Distribución">
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                <DistritosCountMap
                  title="Distritos"
                  items={sig.byDistrito}
                  centroids={stats.distritoCentroids}
                  valueLabel="expedientes"
                />
                <DonutChart title="Promotor" items={sig.byPromotor} maxItems={8} valueLabel="expedientes" />
                <DonutChart title="Tipo de figura" items={sig.byFiguraTipo} maxItems={8} />
                <DonutChart title="Abreviatura figura" items={sig.byTipoFiguraAbrev} maxItems={8} />
                <DonutChart title="Planeamiento" items={sig.byTipoPlaneamiento} maxItems={7} />
                <DonutChart title="Fase actual" items={sig.byFase} maxItems={8} />
                <DonutChart title="Trámite" items={sig.byTramite} maxItems={8} />
                <DonutChart title="Iniciativa" items={sig.byIniciativa} maxItems={6} />
                <DonutChart title="Capa SIGMA" items={sig.byLayer} maxItems={6} />
                <DonutChart title="Órgano" items={sig.byOrgano} maxItems={8} />
              </div>
            </DashboardSection>

            {sig.topViviendas.length > 0 ? (
              <section className="mt-8 overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.03]">
                <div className="border-b border-slate-100 bg-gradient-to-br from-slate-50/90 to-white px-5 py-4">
                  <h2 className="text-lg font-semibold text-slate-900">
                    Mayor densificación (métricas PDF)
                  </h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Solo expedientes con estudio parseado; valores pueden ser atípicos.
                  </p>
                </div>
                <ul className="divide-y divide-slate-100 px-5">
                  {sig.topViviendas.map((row) => (
                    <li
                      key={row.expedienteGrupo}
                      className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
                    >
                      <Link
                        href={sigmaFichaPath(row.expedienteGrupo)}
                        className="font-medium text-[var(--portal-accent)] hover:underline"
                      >
                        {row.expedienteGrupo}
                      </Link>
                      <span className="tabular-nums text-slate-600">
                        {fmt(row.viviendas)} viv.
                        {row.supM2 != null ? ` · ${fmt(Math.round(row.supM2))} m²` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
