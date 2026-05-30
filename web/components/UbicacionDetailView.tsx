"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useState } from "react";
import { DetailBreadcrumbLink } from "@/components/detail/DetailPageShell";
import { ViviendaBadge } from "@/components/detail/SigmaMetricsCards";
import {
  buildUbicacionResumen,
  categoriaExpedienteLabel,
  faseEnLenguajeClaro,
  licenciaDetalleCorto,
} from "@/lib/ubicacion-resumen";
import { LicenciaTitulo } from "@/components/LicenciaTitulo";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import { boletinPath } from "@/lib/boletin-area";
import type { UbicacionFicha, UbicacionSigmaExpediente } from "@/lib/ubicacion";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";

const ProjectsMap = dynamic(
  () => import("./ProjectsMap").then((m) => ({ default: m.ProjectsMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[min(36vh,380px)] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
        Cargando mapa…
      </div>
    ),
  },
);

type TabId = "resumen" | "licencias" | "proyectos";

function ExpedienteCard({
  exp,
  metric,
  tramCount,
}: {
  exp: UbicacionSigmaExpediente;
  metric: SigmaExpedienteMetric | null;
  tramCount: number;
}) {
  return (
    <article className="rounded-xl border border-sky-100 bg-sky-50/30 p-4 shadow-sm transition hover:border-sky-200">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-900 ring-1 ring-sky-200">
          Proyecto urbanístico
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            exp.fase?.toLowerCase().includes("definitiva")
              ? "bg-teal-50 text-teal-800 ring-1 ring-teal-200"
              : "bg-slate-100 text-slate-600 ring-1 ring-slate-200"
          }`}
        >
          {faseEnLenguajeClaro(exp.fase)}
        </span>
        {metric?.genera_vivienda_nueva ? (
          <ViviendaBadge code={metric.genera_vivienda_nueva} />
        ) : null}
      </div>
      <h3 className="mt-2 text-base font-semibold leading-snug text-slate-900">
        {exp.denominacion || "Proyecto urbanístico"}
      </h3>
      {metric?.num_viviendas_max != null ? (
        <p className="mt-1 text-sm text-teal-800">
          Hasta {metric.num_viviendas_max.toLocaleString("es-ES")} viviendas en el ámbito
        </p>
      ) : null}
      <p className="mt-2 text-xs text-slate-500">
        {tramCount > 0
          ? `${tramCount} hito${tramCount !== 1 ? "s" : ""} publicado${tramCount !== 1 ? "s" : ""}`
          : "Sin cronología publicada"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          href={sigmaFichaPath(exp.expediente_grupo)}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
        >
          Ficha del proyecto
        </Link>
        {exp.enlace ? (
          <a
            href={exp.enlace}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            Ayuntamiento ↗
          </a>
        ) : null}
      </div>
    </article>
  );
}

function SignalCard({ text, index }: { text: string; index: number }) {
  const tone =
    index % 3 === 0
      ? "border-amber-100 bg-amber-50/65"
      : index % 3 === 1
        ? "border-teal-100 bg-teal-50/60"
        : "border-sky-100 bg-sky-50/60";
  return (
    <li className={`rounded-xl border px-4 py-3 text-sm leading-relaxed text-slate-700 ${tone}`}>
      {text}
    </li>
  );
}

export function UbicacionDetailView({
  ficha,
  metricsByExpediente = {},
}: {
  ficha: UbicacionFicha;
  metricsByExpediente?: Record<string, SigmaExpedienteMetric | null>;
}) {
  const [tab, setTab] = useState<TabId>("resumen");
  const inv = ficha.inmueble;
  const ndp = inv.ndp_edificio;
  const resumen = buildUbicacionResumen(ficha, metricsByExpediente);
  const proyectosEntorno = ficha.stats.expedientesSigma;
  const actuacionesEdificio = ficha.stats.licenciasTotal;
  const direccion = inv.direccion || "esta ubicación";

  const mapPoints =
    inv.lat != null && inv.lng != null
      ? [{ municipio: inv.direccion || ndp, count: 1, lat: inv.lat, lng: inv.lng }]
      : [];

  const tabs: { id: TabId; label: string; hint?: string }[] = [
    { id: "resumen", label: "Resumen", hint: "Lectura rápida del edificio y la zona" },
    {
      id: "licencias",
      label: "Licencias concedidas",
      hint: "Obras y actuaciones en esta dirección",
    },
    {
      id: "proyectos",
      label: "Proyectos que aplican",
      hint: "Planeamiento urbanístico que afecta a la ubicación",
    },
  ];
  const activeTab = tabs.some((t) => t.id === tab) ? tab : "resumen";

  const licenciasOrdenadas = [...ficha.licencias].sort((a, b) => {
    const da = a.fecha_concesion || a.fecha_alta || "";
    const db = b.fecha_concesion || b.fecha_alta || "";
    return db.localeCompare(da);
  });

  const categoriasOrden = ["local", "sector", "normativa_ciudad"] as const;

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 overflow-x-hidden px-4 py-6 sm:px-6 sm:py-8">
      <nav className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <DetailBreadcrumbLink href="/explore">Mapa Madrid</DetailBreadcrumbLink>
        <span className="text-slate-300">/</span>
        <span className="text-slate-900">{inv.direccion || `NDP ${ndp}`}</span>
      </nav>

      <header className="portal-hero-bg mb-8 overflow-hidden rounded-2xl border border-amber-200/70 shadow-sm">
        <div className="p-6 sm:p-8">
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-amber-100 px-3 py-0.5 text-xs font-semibold text-amber-950 ring-1 ring-amber-200">
              Ficha de ubicación · Edificio
            </span>
            {resumen.hayObraReciente ? (
              <span className="rounded-full bg-white/90 px-3 py-0.5 text-xs font-semibold text-amber-900 ring-1 ring-amber-200/80">
                Actividad reciente
              </span>
            ) : null}
          </div>

          <p className="mt-4 text-sm font-medium uppercase tracking-[0.12em] text-amber-800/80">
            Todo lo que sucede en
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">{direccion}</h1>
          <p className="mt-2 text-base text-slate-600">
            {[inv.distrito, inv.barrio].filter(Boolean).join(" · ") || "Madrid"}
          </p>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-600">
            Licencias y obras en este edificio, más proyectos de planeamiento y normas urbanísticas que
            afectan a la zona — no es la ficha de un solo proyecto, sino la foto de lo que ocurre en torno a esta
            dirección.
          </p>

          <div className="mt-6 flex flex-wrap gap-2">
            <Link
              href={boletinPath(ndp)}
              className="inline-flex rounded-lg bg-[var(--portal-accent)] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[var(--portal-accent-hover)]"
            >
              Boletín de la zona
            </Link>
            <Link
              href="/explore"
              className="inline-flex rounded-lg border border-amber-300 bg-white/90 px-4 py-2.5 text-sm font-semibold text-amber-950 hover:bg-amber-50"
            >
              Ver en el mapa
            </Link>
          </div>
        </div>

        <div className="grid gap-px border-t border-amber-200/60 bg-amber-100/40 sm:grid-cols-3">
          <div className="bg-white/80 px-5 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-800/70">Licencias</p>
            <p className="mt-1 text-xl font-bold text-amber-950">{actuacionesEdificio}</p>
            <p className="text-xs text-slate-500">concedidas en el edificio</p>
          </div>
          <div className="bg-white/80 px-5 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-sky-800/70">Proyectos</p>
            <p className="mt-1 text-xl font-bold text-sky-950">{proyectosEntorno}</p>
            <p className="text-xs text-slate-500">que aplican a la zona</p>
          </div>
          <div className="bg-white/80 px-5 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-teal-800/70">Lectura</p>
            <p className="mt-1 text-xl font-bold text-teal-950">
              {resumen.hayNormativaPgoum ? "Mixta" : proyectosEntorno > 0 ? "Zona" : "Local"}
            </p>
            <p className="text-xs text-slate-500">
              {resumen.hayNormativaPgoum ? "incluye normas generales" : "principalmente actividad local"}
            </p>
          </div>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <aside className="space-y-5 lg:sticky lg:top-6 lg:self-start">
          {mapPoints.length > 0 ? (
            <div className="overflow-hidden rounded-xl border border-amber-200/80 bg-white shadow-sm">
              <p className="border-b border-amber-100 bg-amber-50/70 px-3 py-2 text-xs font-semibold text-amber-900">
                Ubicación del edificio
              </p>
              <ProjectsMap
                points={mapPoints}
                sectorGeoJson={null}
                variant="detail"
                heightClassName="min-h-[220px] h-[min(32vh,320px)]"
              />
              <p className="border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500">
                Punto aproximado del inmueble, no el ámbito de un proyecto.
              </p>
            </div>
          ) : (
            <div className="flex min-h-[220px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
              Sin coordenadas en mapa
            </div>
          )}

          <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-4 text-sm text-amber-950">
            <p className="font-semibold">¿Buscas un proyecto concreto?</p>
            <p className="mt-1 text-xs leading-relaxed text-amber-900/80">
              Los proyectos de planeamiento tienen ficha propia con su ámbito en mapa. Aquí ves el edificio y lo
              que le rodea.
            </p>
          </div>

          <Link
            href={boletinPath(ndp)}
            className="block rounded-xl border border-[var(--portal-accent)]/30 bg-teal-50 px-4 py-3 text-center text-sm font-semibold text-[var(--portal-accent)] hover:bg-teal-100/80"
          >
            Explorar los alrededores
          </Link>
        </aside>

        <div className="min-w-0">
          <div
            className="mb-4 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-100/80 p-1"
            role="tablist"
          >
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={activeTab === t.id}
                title={t.hint}
                onClick={() => setTab(t.id)}
                className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition ${
                  activeTab === t.id
                    ? "bg-white text-amber-950 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tabs.find((t) => t.id === activeTab)?.hint ? (
            <p className="mb-3 text-xs text-slate-500">{tabs.find((t) => t.id === activeTab)?.hint}</p>
          ) : null}

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            {activeTab === "resumen" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">En una frase</h2>
                  <p className="mt-3 text-sm leading-relaxed text-slate-700">{resumen.parrafo}</p>
                </div>

                {resumen.bullets.length > 0 ? (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">Qué conviene saber</h3>
                    <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                      {resumen.bullets.map((b, i) => (
                        <SignalCard key={i} text={b} index={i} />
                      ))}
                    </ul>
                  </div>
                ) : null}

                {resumen.hitos.length > 0 ? (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">Lo más reciente</h3>
                    <ol className="mt-3 space-y-2">
                      {resumen.hitos.slice(0, 5).map((h, i) => (
                        <li
                          key={i}
                          className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 text-sm"
                        >
                          <div className="min-w-0">
                            {h.href ? (
                              <Link
                                href={h.href}
                                className="font-medium text-slate-900 hover:text-[var(--portal-accent)]"
                              >
                                {h.titulo}
                              </Link>
                            ) : (
                              <span className="font-medium text-slate-900">{h.titulo}</span>
                            )}
                            <span className="ml-2 text-xs text-slate-500">{h.detalle}</span>
                          </div>
                          <time className="shrink-0 text-xs tabular-nums text-slate-400">
                            {h.fecha || "—"}
                          </time>
                        </li>
                      ))}
                    </ol>
                    {resumen.hitos.length > 5 ? (
                      <p className="mt-2 text-xs text-slate-500">
                        Hay más hitos en las pestañas de licencias y proyectos.
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <dl className="grid gap-3 border-t border-slate-100 pt-4 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      Referencia municipal
                    </dt>
                    <dd className="mt-1 font-mono text-xs text-slate-700">{ndp}</dd>
                  </div>
                  {inv.distrito ? (
                    <div>
                      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        Distrito
                      </dt>
                      <dd className="mt-1 text-slate-800">{inv.distrito}</dd>
                    </div>
                  ) : null}
                  {inv.barrio ? (
                    <div>
                      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        Barrio
                      </dt>
                      <dd className="mt-1 text-slate-800">{inv.barrio}</dd>
                    </div>
                  ) : null}
                </dl>
              </div>
            )}

            {activeTab === "licencias" && (
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Licencias concedidas</h2>
                <p className="mt-1 mb-4 text-sm text-slate-600">
                  Actuaciones urbanísticas registradas en esta dirección: obras, aperturas, cambios de uso
                  y declaraciones responsables.
                </p>
                {licenciasOrdenadas.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                    No hay licencias concedidas localizadas para este edificio.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {licenciasOrdenadas.map((lic) => (
                      <li
                        key={lic.id}
                        className="rounded-xl border border-amber-100 bg-amber-50/40 p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <time className="text-xs font-semibold tabular-nums text-slate-500">
                            {lic.fecha_concesion || lic.fecha_alta || "Sin fecha"}
                          </time>
                          {lic.uso ? (
                            <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-slate-600 ring-1 ring-amber-100">
                              {lic.uso}
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-2">
                          <LicenciaTitulo licencia={lic} />
                          <p className="mt-0.5 text-sm text-slate-600">{licenciaDetalleCorto(lic)}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {activeTab === "proyectos" && (
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Proyectos que aplican</h2>
                <p className="mt-1 mb-4 text-sm text-slate-600">
                  Proyectos de planeamiento cuyo ámbito incluye esta dirección — también normas
                  generales de ciudad (PGOUM, catálogos…) si el edificio cae dentro de su ámbito.
                </p>
                {ficha.expedientesSigma.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                    Ningún proyecto de planeamiento enlazado a esta ubicación.
                  </p>
                ) : (
                  <div className="space-y-6">
                    {categoriasOrden.map((cat) => {
                      const items = resumen.expedientesPorCategoria[cat];
                      if (!items.length) return null;
                      return (
                        <div key={cat}>
                          <h3 className="mb-3 text-sm font-semibold text-slate-700">
                            {categoriaExpedienteLabel(cat)}
                            <span className="ml-2 font-normal text-slate-400">({items.length})</span>
                          </h3>
                          <ul className="grid gap-3 sm:grid-cols-2">
                            {items.map((exp) => (
                              <li key={exp.expediente_grupo}>
                                <ExpedienteCard
                                  exp={exp}
                                  metric={metricsByExpediente[exp.expediente_grupo] ?? null}
                                  tramCount={(ficha.tramitacionSigma[exp.expediente_grupo] || []).length}
                                />
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <p className="mt-8 text-center text-xs text-slate-400">
        Datos del Ayuntamiento de Madrid y expedientes urbanísticos enlazados.
      </p>
    </main>
  );
}
