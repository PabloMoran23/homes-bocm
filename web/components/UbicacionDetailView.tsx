"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import {
  DetailBreadcrumbLink,
  DetailPageShell,
} from "@/components/detail/DetailPageShell";
import { ViviendaBadge } from "@/components/detail/SigmaMetricsCards";
import {
  buildUbicacionResumen,
  categoriaExpedienteLabel,
  faseEnLenguajeClaro,
} from "@/lib/ubicacion-resumen";
import { LicenciaTitulo } from "@/components/LicenciaTitulo";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import type { UbicacionFicha, UbicacionSigmaExpediente } from "@/lib/ubicacion";
import { sigmaSlugFromExpediente } from "@/lib/ubicacion";

const ProjectsMap = dynamic(
  () => import("./ProjectsMap").then((m) => ({ default: m.ProjectsMap })),
  { ssr: false, loading: () => <div className="h-48 animate-pulse rounded-xl bg-slate-100" /> },
);

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
    <article className="rounded-xl border border-slate-200/90 bg-white p-4 shadow-sm transition hover:border-teal-200/80">
      <div className="flex flex-wrap items-center gap-2">
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
        {exp.denominacion || "Expediente urbanístico"}
      </h3>
      {metric?.num_viviendas_max != null ? (
        <p className="mt-1 text-sm text-teal-800">
          Hasta {metric.num_viviendas_max.toLocaleString("es-ES")} viviendas en el ámbito
        </p>
      ) : null}
      <p className="mt-2 text-xs text-slate-500">
        {tramCount > 0 ? `${tramCount} pasos en tramitación` : "Sin historial en visor"}
        <span className="mx-1.5 text-slate-300">·</span>
        <span className="font-mono">{exp.exp_numero_original}</span>
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          href={`/sigma/${sigmaSlugFromExpediente(exp.expediente_grupo)}`}
          className="rounded-lg bg-[var(--portal-accent)] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[var(--portal-accent-hover)]"
        >
          Ver detalle
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

function Div({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={className}>{children}</div>;
}

export function UbicacionDetailView({
  ficha,
  metricsByExpediente = {},
}: {
  ficha: UbicacionFicha;
  metricsByExpediente?: Record<string, SigmaExpedienteMetric | null>;
}) {
  const inv = ficha.inmueble;
  const ndp = inv.ndp_edificio;
  const resumen = buildUbicacionResumen(ficha, metricsByExpediente);

  const mapPoints =
    inv.lat != null && inv.lng != null
      ? [{ municipio: inv.direccion || ndp, count: 1, lat: inv.lat, lng: inv.lng }]
      : [];

  const hero = (
    <header className="portal-hero-bg rounded-2xl border border-teal-200/40 px-5 py-6 sm:px-7">
      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--portal-warm)]">
        Tu dirección · Madrid
      </p>
      <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
        {inv.direccion || "Sin dirección registrada"}
      </h1>
      <p className="mt-2 text-slate-600">
        {[inv.distrito, inv.barrio].filter(Boolean).join(" · ")}
      </p>
    </header>
  );

  const aside =
    mapPoints.length > 0 ? (
      <Div className="overflow-hidden rounded-xl border border-slate-200 shadow-sm">
        <p className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
          Ubicación en el mapa
        </p>
        <ProjectsMap points={mapPoints} sectorGeoJson={null} variant="detail" heightClassName="h-52" />
        <p className="px-3 py-2 text-center text-xs">
          <Link href="/explore" className="font-medium text-[var(--portal-accent)] hover:underline">
            Explorar alrededor
          </Link>
        </p>
      </Div>
    ) : null;

  const categoriasOrden = ["local", "sector", "normativa_ciudad"] as const;

  return (
    <DetailPageShell
      breadcrumb={
        <>
          <DetailBreadcrumbLink href="/explore">Mapa Madrid</DetailBreadcrumbLink>
          <span className="text-slate-300">/</span>
          <span className="text-slate-900">{inv.direccion || `NDP ${ndp}`}</span>
        </>
      }
      hero={hero}
      aside={aside}
      footer={
        <p className="text-center text-xs text-slate-400">
          Datos: licencias open data Ayto. Madrid · planeamiento SIGMA · NDP{" "}
          <span className="font-mono">{ndp}</span>
        </p>
      }
    >
      {/* Resumen principal */}
      <section className="rounded-2xl border border-teal-200/60 bg-gradient-to-br from-teal-50/90 via-white to-white p-5 shadow-sm sm:p-7">
        <h2 className="text-lg font-bold text-slate-900">Qué está pasando aquí</h2>
        <p className="mt-3 text-base leading-relaxed text-slate-700">{resumen.parrafo}</p>
        <ul className="mt-4 space-y-2">
          {resumen.bullets.map((b, i) => (
            <li key={i} className="flex gap-2 text-sm leading-relaxed text-slate-600">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--portal-accent)]" />
              {b}
            </li>
          ))}
        </ul>
        <div className="mt-5 flex flex-wrap gap-2">
          {resumen.hayObraReciente ? (
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
              {ficha.stats.licenciasTotal} licencia{ficha.stats.licenciasTotal !== 1 ? "s" : ""} en el edificio
            </span>
          ) : null}
          {ficha.stats.expedientesSigma > 0 ? (
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
              {ficha.stats.expedientesSigma} ámbito{ficha.stats.expedientesSigma !== 1 ? "s" : ""} de planeamiento
            </span>
          ) : null}
        </div>
      </section>

      {/* Actividad en el edificio */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <h2 className="text-lg font-semibold text-slate-900">Actividad en este edificio</h2>
        <p className="mt-1 text-sm text-slate-600">
          Obras y tramitaciones con licencia en esta dirección (no incluye normas generales de toda la ciudad).
        </p>
        {resumen.licenciasRecientes.length === 0 ? (
          <p className="mt-5 text-sm text-slate-500">Sin licencias en el registro municipal para este NDP.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {resumen.licenciasRecientes.map((lic) => (
              <li
                key={lic.id}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl bg-slate-50/80 px-4 py-3 ring-1 ring-slate-100"
              >
                <div>
                  <LicenciaTitulo tipoExpediente={lic.tipo_expediente} />
                  <p className="mt-0.5 text-sm text-slate-600">
                    {[lic.uso, lic.procedimiento?.replace(/Procedimiento\s+/i, "")]
                      .filter(Boolean)
                      .join(" · ") || "Sin detalle de uso"}
                  </p>
                </div>
                <time className="shrink-0 text-sm tabular-nums text-slate-500">
                  {lic.fecha_concesion || lic.fecha_alta || "—"}
                </time>
              </li>
            ))}
          </ul>
        )}
        {ficha.stats.licenciasTotal > resumen.licenciasRecientes.length ? (
          <p className="mt-3 text-xs text-slate-500">
            +{ficha.stats.licenciasTotal - resumen.licenciasRecientes.length} licencias más en el histórico.
          </p>
        ) : null}
      </section>

      {/* Línea de tiempo mezclada */}
      {resumen.hitos.length > 0 ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-900">Cronología reciente</h2>
          <p className="mt-1 text-sm text-slate-600">Lo más reciente primero (licencias y hitos de planeamiento).</p>
          <ol className="relative mt-5 space-y-0 border-l-2 border-teal-100 pl-5">
            {resumen.hitos.map((h, i) => (
              <li key={i} className="relative pb-5 last:pb-0">
                <span
                  className={`absolute -left-[1.35rem] top-1 flex h-3 w-3 rounded-full ring-2 ring-white ${
                    h.tipo === "licencia" ? "bg-amber-400" : "bg-sky-500"
                  }`}
                />
                <p className="text-xs tabular-nums text-slate-400">{h.fecha || "Sin fecha"}</p>
                {h.href ? (
                  <Link href={h.href} className="mt-0.5 block font-medium text-slate-900 hover:text-[var(--portal-accent)]">
                    {h.titulo}
                  </Link>
                ) : (
                  <p className="mt-0.5 font-medium text-slate-900">{h.titulo}</p>
                )}
                <p className="text-sm text-slate-500">{h.detalle}</p>
                {h.nota ? <p className="mt-0.5 text-xs text-slate-500">{h.nota}</p> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {/* Planeamiento por categoría */}
      {ficha.expedientesSigma.length > 0 ? (
        <section className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Planeamiento que afecta a la zona</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-600">
              El punto cae dentro de estos ámbitos SIGMA. Los cambios del PGOUM suelen regular toda la ciudad; los
              planes de sector o actuaciones locales son los que más suelen explicar un proyecto concreto cerca.
            </p>
          </div>

          {categoriasOrden.map((cat) => {
            const items = resumen.expedientesPorCategoria[cat];
            if (!items.length) return null;
            return (
              <div key={cat}>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
                  {categoriaExpedienteLabel(cat)}
                  <span className="ml-2 font-normal normal-case text-slate-400">({items.length})</span>
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
        </section>
      ) : null}

      {/* Detalle técnico colapsable */}
      <details className="group rounded-2xl border border-slate-200 bg-slate-50/50">
        <summary className="cursor-pointer list-none px-5 py-4 text-sm font-semibold text-slate-700 marker:content-none sm:px-6">
          <span className="flex items-center justify-between gap-2">
            Ver datos técnicos completos
            <span className="text-slate-400 transition group-open:rotate-180">▼</span>
          </span>
        </summary>
        <div className="border-t border-slate-200 px-5 pb-5 pt-4 sm:px-6">
          <p className="mb-3 text-xs text-slate-500">Tabla original de licencias (open data 300193).</p>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="bg-slate-50 font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-2 py-2">Fecha</th>
                  <th className="px-2 py-2">Tipo</th>
                  <th className="px-2 py-2">Uso</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ficha.licencias.map((lic) => (
                  <tr key={lic.id}>
                    <td className="whitespace-nowrap px-2 py-2 tabular-nums">
                      {lic.fecha_concesion || lic.fecha_alta || "—"}
                    </td>
                    <td className="max-w-[200px] px-2 py-2">{lic.tipo_expediente || "—"}</td>
                    <td className="px-2 py-2">{lic.uso || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </DetailPageShell>
  );
}

