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
  licenciaDetalleCorto,
} from "@/lib/ubicacion-resumen";
import { LicenciaTitulo } from "@/components/LicenciaTitulo";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import { boletinPath } from "@/lib/boletin-area";
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
        {exp.denominacion || "Proyecto urbanístico"}
      </h3>
      {metric?.num_viviendas_max != null ? (
        <p className="mt-1 text-sm text-teal-800">
          Hasta {metric.num_viviendas_max.toLocaleString("es-ES")} viviendas en el ámbito
        </p>
      ) : null}
      <p className="mt-2 text-xs text-slate-500">
        {tramCount > 0 ? `${tramCount} hito${tramCount !== 1 ? "s" : ""} publicado${tramCount !== 1 ? "s" : ""}` : "Sin cronología publicada"}
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
      <details className="mt-3 rounded-lg bg-slate-50/80 px-3 py-2">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-800">
          Ver referencia municipal
        </summary>
        <p className="mt-2 font-mono text-xs text-slate-500">{exp.exp_numero_original}</p>
      </details>
    </article>
  );
}

function Div({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={className}>{children}</div>;
}

function QuickStat({
  label,
  value,
  detail,
  tone = "teal",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "teal" | "amber" | "sky";
}) {
  const toneClass =
    tone === "amber"
      ? "border-amber-200 bg-amber-50/80 text-amber-950"
      : tone === "sky"
        ? "border-sky-200 bg-sky-50/80 text-sky-950"
        : "border-teal-200 bg-teal-50/80 text-teal-950";

  return (
    <div className={`rounded-2xl border px-4 py-3 shadow-sm ${toneClass}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
      <p className="mt-1 text-xs leading-snug opacity-75">{detail}</p>
    </div>
  );
}

function SectionHeader({
  label,
  title,
  description,
}: {
  label?: string;
  title: string;
  description?: string;
}) {
  return (
    <div>
      {label ? (
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--portal-accent)]">
          {label}
        </p>
      ) : null}
      <h2 className="mt-1 text-xl font-bold tracking-tight text-slate-950">{title}</h2>
      {description ? <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-600">{description}</p> : null}
    </div>
  );
}

function SignalCard({ text, index }: { text: string; index: number }) {
  const tone =
    index % 3 === 0
      ? "border-teal-100 bg-teal-50/65"
      : index % 3 === 1
        ? "border-amber-100 bg-amber-50/60"
        : "border-sky-100 bg-sky-50/60";
  return (
    <li className={`rounded-2xl border px-4 py-3 text-sm leading-relaxed text-slate-700 shadow-sm ${tone}`}>
      <span className="mb-2 block h-1.5 w-8 rounded-full bg-[var(--portal-accent)]/70" aria-hidden />
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
  const inv = ficha.inmueble;
  const ndp = inv.ndp_edificio;
  const resumen = buildUbicacionResumen(ficha, metricsByExpediente);
  const proyectosEntorno = ficha.stats.expedientesSigma;
  const actuacionesEdificio = ficha.stats.licenciasTotal;

  const mapPoints =
    inv.lat != null && inv.lng != null
      ? [{ municipio: inv.direccion || ndp, count: 1, lat: inv.lat, lng: inv.lng }]
      : [];

  const hero = (
    <header className="portal-hero-bg overflow-hidden rounded-3xl border border-teal-200/50 shadow-sm">
      <div className="grid gap-5 p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)] lg:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--portal-warm)]">
            Ficha de ubicación · Madrid
          </p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
            {inv.direccion || "Sin dirección registrada"}
          </h1>
          <p className="mt-2 text-slate-600">
            {[inv.distrito, inv.barrio].filter(Boolean).join(" · ") || "Madrid"}
          </p>
        </div>
        <div className="rounded-2xl border border-white/80 bg-white/75 p-4 shadow-sm backdrop-blur">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Lectura rápida</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-700">
            Actividad del edificio, proyectos cercanos y normas urbanísticas que pueden afectar a esta zona.
          </p>
        </div>
      </div>
    </header>
  );

  const aside =
    mapPoints.length > 0 ? (
      <Div className="overflow-hidden rounded-2xl border border-teal-100/80 bg-white shadow-sm">
        <div className="border-b border-teal-100 bg-teal-50/60 px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-900">Ubicación en el mapa</p>
          <p className="mt-0.5 text-[11px] text-teal-900/70">Centro aproximado del edificio.</p>
        </div>
        <ProjectsMap points={mapPoints} sectorGeoJson={null} variant="detail" heightClassName="h-52" />
        <div className="grid grid-cols-2 gap-2 border-t border-slate-100 p-3">
          <div className="rounded-xl bg-amber-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-900/70">
              Edificio
            </p>
            <p className="mt-1 text-lg font-bold text-amber-950">{actuacionesEdificio}</p>
          </div>
          <div className="rounded-xl bg-sky-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-sky-900/70">
              Entorno
            </p>
            <p className="mt-1 text-lg font-bold text-sky-950">{proyectosEntorno}</p>
          </div>
          <Link
            href={boletinPath(ndp)}
            className="col-span-2 rounded-xl bg-[var(--portal-accent)] px-3 py-2 text-center text-xs font-semibold text-white hover:bg-[var(--portal-accent-hover)]"
          >
            Explora los alrededores
          </Link>
        </div>
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
          Datos del Ayuntamiento de Madrid y expedientes urbanísticos enlazados.
        </p>
      }
    >
      {/* Resumen principal */}
      <section className="rounded-3xl border border-teal-200/60 bg-gradient-to-br from-teal-50/90 via-white to-sky-50/60 p-5 shadow-sm sm:p-7">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
          <div>
            <SectionHeader label="Resumen" title="Qué está pasando aquí" />
            <p className="mt-3 text-base leading-relaxed text-slate-700">{resumen.parrafo}</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
            <QuickStat
              label="Edificio"
              value={String(actuacionesEdificio)}
              detail={actuacionesEdificio === 1 ? "actuación localizada" : "actuaciones localizadas"}
              tone="amber"
            />
            <QuickStat
              label="Entorno"
              value={String(proyectosEntorno)}
              detail={proyectosEntorno === 1 ? "proyecto cercano" : "proyectos cercanos"}
              tone="sky"
            />
            <QuickStat
              label="Lectura"
              value={resumen.hayNormativaPgoum ? "Mixta" : proyectosEntorno > 0 ? "Zona" : "Edificio"}
              detail={resumen.hayNormativaPgoum ? "incluye normas generales" : "principalmente actividad local"}
            />
          </div>
        </div>
        <ul className="mt-5 grid gap-3 sm:grid-cols-2">
          {resumen.bullets.map((b, i) => (
            <SignalCard key={i} text={b} index={i} />
          ))}
        </ul>
        <div className="mt-5 flex flex-wrap gap-2 border-t border-white/80 pt-4">
          {resumen.hayObraReciente ? (
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
              {ficha.stats.licenciasTotal} actuación{ficha.stats.licenciasTotal !== 1 ? "es" : ""} en el edificio
            </span>
          ) : null}
          {ficha.stats.expedientesSigma > 0 ? (
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
              {ficha.stats.expedientesSigma} proyecto{ficha.stats.expedientesSigma !== 1 ? "s" : ""} en el entorno
            </span>
          ) : null}
        </div>
      </section>

      {/* Actividad en el edificio */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <SectionHeader
            label="Edificio"
            title="Actividad en este edificio"
            description="Obras, aperturas o cambios registrados para esta dirección. No incluye normas generales de toda la ciudad."
          />
          {resumen.licenciasRecientes.length > 0 ? (
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900 ring-1 ring-amber-200">
              Últimas {resumen.licenciasRecientes.length}
            </span>
          ) : null}
        </div>
        {resumen.licenciasRecientes.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-6 text-center text-sm text-slate-500">
            Sin actividad municipal localizada para esta dirección.
          </div>
        ) : (
          <ul className="mt-5 grid gap-3 md:grid-cols-2">
            {resumen.licenciasRecientes.map((lic) => (
              <li
                key={lic.id}
                className="rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50/70 to-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="mt-1 h-9 w-9 shrink-0 rounded-full bg-amber-100 ring-4 ring-white" aria-hidden />
                  <time className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-semibold tabular-nums text-slate-500 ring-1 ring-amber-100">
                    {lic.fecha_concesion || lic.fecha_alta || "Sin fecha"}
                  </time>
                </div>
                <div className="mt-3">
                  <LicenciaTitulo tipoExpediente={lic.tipo_expediente} />
                  <p className="mt-0.5 text-sm text-slate-600">
                    {licenciaDetalleCorto(lic)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
        {ficha.stats.licenciasTotal > resumen.licenciasRecientes.length ? (
          <p className="mt-3 text-xs text-slate-500">
            +{ficha.stats.licenciasTotal - resumen.licenciasRecientes.length} actuaciones más en el histórico.
          </p>
        ) : null}
      </section>

      {/* Línea de tiempo mezclada */}
      {resumen.hitos.length > 0 ? (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <SectionHeader
            label="Tiempo"
            title="Cronología reciente"
            description="Lo más reciente primero: actividad del edificio e hitos de proyectos urbanísticos cercanos."
          />
          <ol className="mt-5 grid gap-3 md:grid-cols-2">
            {resumen.hitos.map((h, i) => (
              <li
                key={i}
                className={`rounded-2xl border p-4 shadow-sm ${
                  h.tipo === "licencia"
                    ? "border-amber-100 bg-amber-50/45"
                    : "border-sky-100 bg-sky-50/45"
                }`}
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span
                    className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                      h.tipo === "licencia"
                        ? "bg-amber-100 text-amber-900"
                        : "bg-sky-100 text-sky-900"
                    }`}
                  >
                    {h.tipo === "licencia" ? "Edificio" : "Entorno"}
                  </span>
                  <p className="text-xs tabular-nums text-slate-500">{h.fecha || "Sin fecha"}</p>
                </div>
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
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <SectionHeader
            label="Entorno"
            title="Proyectos y normas que afectan a la zona"
            description="Esta dirección cae dentro de estos ámbitos. Algunas fichas son proyectos cercanos; otras son cambios generales de normativa que pueden afectar a muchas zonas de Madrid."
          />

          <div className="mt-5 space-y-6">
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
          </div>
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
          <dl className="mb-5 grid gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Identificador municipal del edificio
              </dt>
              <dd className="mt-1 font-mono text-xs text-slate-800">{ndp}</dd>
            </div>
            {inv.lat != null && inv.lng != null ? (
              <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
                <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Coordenadas
                </dt>
                <dd className="mt-1 font-mono text-xs text-slate-800">
                  {inv.lat.toFixed(5)}, {inv.lng.toFixed(5)}
                </dd>
              </div>
            ) : null}
          </dl>
          <p className="mb-3 text-xs text-slate-500">Tabla fuente de actuaciones municipales asociadas a esta dirección.</p>
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

