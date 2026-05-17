"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { NtiDocumentList } from "@/components/project-detail/NtiDocumentList";
import { RelatedBoletines } from "@/components/project-detail/RelatedBoletines";
import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import { filterSectorGeoJsonForProjects } from "@/lib/filter-sector-geo";
import {
  coordSourceLabel,
  formatSigmaDateYmdUTC,
  hasValue,
  projectHeadline,
  relevanciaBadgeClass,
  relevanciaLabel,
  sigmaCatalogSourceLabel,
  sigmaLayerKindLabel,
  sigmaMatchLabel,
} from "@/lib/project-display";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import {
  loadSigmaNtiLinkedBundle,
  lookupSigmaNtiGrupo,
  type SigmaNtiLinkedBundle,
} from "@/lib/sigma-nti-linked";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import type { Project } from "@/lib/types";
import type { MapPoint } from "./ProjectsMap";

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

type TabId = "resumen" | "ayto" | "documentos" | "boletin" | "relacionados";

const TABS: { id: TabId; label: string; show: (p: Project) => boolean }[] = [
  { id: "resumen", label: "Resumen", show: () => true },
  { id: "ayto", label: "Ayto. Madrid", show: (p) => Boolean(p.sigmaExpediente) },
  {
    id: "documentos",
    label: "Documentos",
    show: (p) =>
      Boolean(
        p.sigmaVisorNtiDocumentosTotal ||
          (p.sigmaVisorNtiDocumentosMuestra?.length ?? 0) > 0 ||
          (p.sigmaVisorDocumentacionUrls?.length ?? 0) > 0,
      ),
  },
  { id: "boletin", label: "Datos BOCM", show: () => true },
  {
    id: "relacionados",
    label: "Relacionados",
    show: (p) => (p.sigmaBoletinMismaExpediente?.length ?? 0) > 0,
  },
];

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  if (value == null || value === "" || value === "—") return null;
  return (
    <div className="grid gap-0.5 border-b border-slate-100 py-3 last:border-0 sm:grid-cols-[minmax(0,10rem)_1fr] sm:gap-4">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`text-sm text-slate-900 ${mono ? "break-all font-mono text-xs" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "teal" | "sky" | "amber";
}) {
  const tones = {
    neutral: "bg-white ring-slate-200",
    teal: "bg-teal-50/80 ring-teal-200/80",
    sky: "bg-sky-50/80 ring-sky-200/80",
    amber: "bg-amber-50/80 ring-amber-200/80",
  };
  return (
    <div className={`rounded-xl p-4 ring-1 ${tones[tone]}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-bold leading-tight text-slate-900">{value}</p>
      {sub ? <p className="mt-0.5 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}

export function ProjectDetailView({ project: p }: { project: Project }) {
  const [sectorGeoJson, setSectorGeoJson] = useState<SectorFeatureCollection | null>(null);
  const [ntiBundle, setNtiBundle] = useState<SigmaNtiLinkedBundle | null>(null);
  const [tab, setTab] = useState<TabId>("resumen");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/data/sector-geometries.geojson");
        if (!res.ok) return;
        const fc = (await res.json()) as SectorFeatureCollection;
        if (!cancelled) setSectorGeoJson(fc);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!p.sigmaExpediente) return;
    let cancelled = false;
    loadSigmaNtiLinkedBundle().then((b) => {
      if (!cancelled) setNtiBundle(b);
    });
    return () => {
      cancelled = true;
    };
  }, [p.sigmaExpediente]);

  const ntiLinked = useMemo(
    () => lookupSigmaNtiGrupo(ntiBundle, p.sigmaExpediente),
    [ntiBundle, p.sigmaExpediente],
  );

  const sectorGeo = useMemo(
    () => filterSectorGeoJsonForProjects(sectorGeoJson, [p]),
    [sectorGeoJson, p],
  );

  const mapPoints: MapPoint[] = useMemo(() => {
    if (p.lat == null || p.lng == null) return [];
    return [
      {
        municipio: p.municipio || p.territorioLabel,
        count: 1,
        lat: p.lat,
        lng: p.lng,
      },
    ];
  }, [p]);

  const categorias = useMemo(() => {
    if (!hasValue(p.categoriasTematicas)) return [];
    return p.categoriasTematicas.split(";").map((c) => c.trim()).filter(Boolean);
  }, [p.categoriasTematicas]);

  const headline = projectHeadline(p);
  const visorH1 = p.sigmaVisorCabecera?.h1;
  const visorH2 = p.sigmaVisorCabecera?.h2;
  const tramCount = p.sigmaVisorTramitacion?.length ?? 0;
  const docTotal = ntiLinked?.stats.total ?? p.sigmaVisorNtiDocumentosTotal ?? 0;
  const docLocal = ntiLinked?.stats.downloaded ?? 0;

  const visibleTabs = TABS.filter((t) => t.show(p));
  const activeTab = visibleTabs.some((t) => t.id === tab) ? tab : visibleTabs[0]?.id ?? "resumen";

  const bocmVsSigma =
    hasValue(p.estadoTramitacion) && hasValue(p.sigmaFase)
      ? { bocm: p.estadoTramitacion, sigma: p.sigmaFase }
      : null;

  return (
    <main className="mx-auto max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
      <nav className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <Link href="/explore" className="font-medium text-[var(--portal-accent)] hover:underline">
          ← Mapa Madrid
        </Link>
        {p.sigmaExpediente ? (
          <>
            <span className="text-slate-300">/</span>
            <Link
              href={sigmaFichaPath(String(p.sigmaExpediente))}
              className="hover:text-slate-800 hover:underline"
            >
              Proyecto urbanístico
            </Link>
          </>
        ) : null}
      </nav>

      {/* Hero */}
      <header className="portal-hero-bg mb-8 overflow-hidden rounded-2xl border border-slate-200/80 shadow-sm">
        <div className="p-6 sm:p-8">
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-white/90 px-3 py-0.5 text-xs font-semibold text-[var(--portal-accent)] ring-1 ring-teal-200/80">
              {p.territorioLabel}
            </span>
            <span
              className={`rounded-full px-3 py-0.5 text-xs font-semibold ring-1 ${relevanciaBadgeClass(p.esRelevante)}`}
            >
              {relevanciaLabel(p.esRelevante)}
            </span>
            {p.sigmaEnIp ? (
              <span className="rounded-full bg-sky-100 px-3 py-0.5 text-xs font-semibold text-sky-900 ring-1 ring-sky-200">
                Información pública
              </span>
            ) : null}
            {hasValue(p.tipoInstrumento) ? (
              <span className="rounded-full bg-white/80 px-3 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                {p.tipoInstrumento}
              </span>
            ) : null}
          </div>

          <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            {visorH1 || headline}
          </h1>
          {visorH2 ? <p className="mt-1 text-base text-slate-600">{visorH2}</p> : null}
          {!visorH2 && (hasValue(p.municipio) || hasValue(p.nombreSector)) ? (
            <p className="mt-2 text-base text-slate-600">
              {[p.municipio, p.nombreSector].filter(hasValue).join(" · ")}
            </p>
          ) : null}

          {p.sigmaExpediente ? (
            <p className="mt-3 font-mono text-sm font-medium text-teal-900">
              Expediente {p.sigmaExpediente}
            </p>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2">
            {p.pdfUrl ? (
              <a
                href={p.pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-lg bg-[var(--portal-accent)] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[var(--portal-accent-hover)]"
              >
                PDF BOCM
              </a>
            ) : null}
            {p.sigmaExpediente ? (
              <Link
                href={sigmaFichaPath(p.sigmaExpediente)}
                className="inline-flex items-center rounded-lg border border-sky-300 bg-white/90 px-4 py-2.5 text-sm font-semibold text-sky-950 hover:bg-sky-50"
              >
                Ficha del proyecto
              </Link>
            ) : null}
            {hasValue(p.sigmaVisorUrl) ? (
              <a
                href={p.sigmaVisorUrl!}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-lg border border-teal-300 bg-white/90 px-4 py-2.5 text-sm font-semibold text-teal-950 hover:bg-teal-50"
              >
                Visor municipal
              </a>
            ) : null}
            {p.sigmaEnlace && p.sigmaEnlace !== p.sigmaVisorUrl ? (
              <a
                href={p.sigmaEnlace}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-lg border border-sky-200 bg-white/90 px-4 py-2.5 text-sm font-semibold text-sky-900 hover:bg-sky-50"
              >
                Visor del Ayuntamiento (GIS)
              </a>
            ) : null}
          </div>
        </div>

        <div className="grid gap-px border-t border-slate-200/80 bg-slate-200/50 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Boletín" value={p.bocmDate || "—"} sub={p.artNum ? `Art. ${p.artNum}` : undefined} />
          {hasValue(p.estadoTramitacion) ? (
            <KpiCard label="Estado (BOCM)" value={p.estadoTramitacion} tone="amber" />
          ) : null}
          {hasValue(p.sigmaFase) ? (
            <KpiCard label="Fase" value={p.sigmaFase!} tone="sky" />
          ) : null}
          {tramCount > 0 ? (
            <KpiCard
              label="Pasos tramitación"
              value={String(tramCount)}
              sub="Visor Ayto."
              tone="teal"
            />
          ) : docTotal > 0 ? (
            <KpiCard
              label="Documentos NTI"
              value={String(docTotal)}
              sub={docLocal > 0 ? `${docLocal} en disco` : undefined}
              tone="teal"
            />
          ) : null}
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        {/* Sidebar */}
        <aside className="space-y-5 lg:sticky lg:top-6 lg:self-start">
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <ProjectsMap
              points={mapPoints}
              sectorGeoJson={sectorGeo}
              dataScope="full"
              variant="detail"
              heightClassName="min-h-[220px] h-[min(32vh,320px)]"
            />
            <p className="border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500">
              {p.lat != null
                ? coordSourceLabel(p.coordSource)
                : sectorGeo?.features?.length
                  ? "Geometría de sector"
                  : "Sin ubicación"}
            </p>
          </div>

          {bocmVsSigma ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                BOCM y planeamiento
              </h3>
              <div className="mt-3 space-y-3 text-sm">
                <div>
                  <p className="text-[10px] font-semibold uppercase text-amber-800">Anuncio</p>
                  <p className="font-medium text-slate-900">{bocmVsSigma.bocm}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase text-sky-800">Catálogo</p>
                  <p className="font-medium text-slate-900">{bocmVsSigma.sigma}</p>
                </div>
              </div>
            </div>
          ) : null}

          {p.sigmaMatchType ? (
            <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
              Enlace BOCM ↔ proyecto: <strong>{sigmaMatchLabel(p.sigmaMatchType)}</strong>
              {p.sigmaMatchScore != null ? ` (${p.sigmaMatchScore})` : ""}
            </p>
          ) : null}
        </aside>

        {/* Main panel */}
        <div className="min-w-0">
          <div
            className="mb-4 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-100/80 p-1"
            role="tablist"
          >
            {visibleTabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={activeTab === t.id}
                onClick={() => setTab(t.id)}
                className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition ${
                  activeTab === t.id
                    ? "bg-white text-teal-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            {activeTab === "resumen" && (
              <div className="space-y-6">
                {hasValue(p.resumen) ? (
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">Resumen del anuncio</h2>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                      {p.resumen}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">Sin resumen generado.</p>
                )}
                {p.sigmaDenominacion && p.sigmaDenominacion !== visorH1 ? (
                  <div className="rounded-lg bg-slate-50 px-4 py-3 text-sm">
                    <span className="font-medium text-slate-500">Denominación · </span>
                    {p.sigmaDenominacion}
                  </div>
                ) : null}
              </div>
            )}

            {activeTab === "ayto" && p.sigmaExpediente && (
              <div className="space-y-8">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">Datos del Ayuntamiento</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Metadatos del índice geográfico urbanístico municipal.
                  </p>
                  <dl className="mt-4 divide-y divide-slate-100">
                    <DetailRow label="Referencia" value={p.sigmaExpediente} mono />
                    <DetailRow label="Denominación" value={p.sigmaDenominacion} />
                    <DetailRow label="Tipo figura" value={p.sigmaTipoFigura} />
                    <DetailRow label="Código figura" value={p.sigmaFiguraCodigo} mono />
                    <DetailRow label="Órgano tramitador" value={p.sigmaOrganoTramitador} />
                    <DetailRow label="Fase vigente" value={p.sigmaFase} />
                    <DetailRow
                      label="Aprobación"
                      value={formatSigmaDateYmdUTC(p.sigmaFechaAprobacion ?? null) ?? undefined}
                    />
                    <DetailRow
                      label="Info. pública"
                      value={(() => {
                        const ini = formatSigmaDateYmdUTC(p.sigmaInfopublicaInicio ?? null);
                        const fin = formatSigmaDateYmdUTC(p.sigmaInfopublicaFin ?? null);
                        if (!ini && !fin) return null;
                        return [ini, fin ? `→ ${fin}` : null].filter(Boolean).join(" ");
                      })()}
                    />
                    <DetailRow
                      label="Origen"
                      value={sigmaCatalogSourceLabel(p.sigmaCatalogSource) ?? undefined}
                    />
                    <DetailRow
                      label="Capa"
                      value={sigmaLayerKindLabel(p.sigmaSigmaLayerKind) ?? undefined}
                    />
                  </dl>
                </div>

                {tramCount > 0 ? (
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">Cronología de tramitación</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      Historial del visor de seguimiento (
                      {hasValue(p.sigmaVisorFetchedAt)
                        ? new Date(p.sigmaVisorFetchedAt!).toLocaleString("es-ES")
                        : "última sincronización"}
                      ).
                    </p>
                    <div className="mt-6">
                      <TramitacionTimeline rows={p.sigmaVisorTramitacion!} />
                    </div>
                  </div>
                ) : (
                  <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    Este proyecto no devolvió pasos de tramitación en el visor. La fase indicada arriba
                    refleja el estado del catálogo GIS.
                  </p>
                )}
              </div>
            )}

            {activeTab === "documentos" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">Documentación electrónica</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Árbol NTI y enlaces del visor documental del Ayuntamiento.
                  </p>
                </div>

                {(p.sigmaVisorDocumentacionUrls?.length ?? 0) > 0 ? (
                  <ul className="flex flex-wrap gap-2">
                    {p.sigmaVisorDocumentacionUrls!.map((u) => (
                      <li key={u}>
                        <a
                          href={u}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex rounded-lg border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-900 hover:bg-teal-100"
                        >
                          {u.includes("listado.htm") ? "Listado NTI" : "Portal documentación"}
                        </a>
                      </li>
                    ))}
                  </ul>
                ) : null}

                <NtiDocumentList
                  linked={ntiLinked}
                  muestra={p.sigmaVisorNtiDocumentosMuestra}
                  totalVisor={p.sigmaVisorNtiDocumentosTotal}
                  listadoUrl={p.sigmaVisorNtiListadoUrl}
                />

                {!ntiLinked &&
                !(p.sigmaVisorNtiDocumentosMuestra?.length) &&
                !p.sigmaVisorNtiDocumentosTotal ? (
                  <p className="text-sm text-slate-500">
                    Sin árbol NTI para este expediente en nuestra base (sólo aplica a parte del
                    catálogo municipal).
                  </p>
                ) : null}
              </div>
            )}

            {activeTab === "boletin" && (
              <dl className="divide-y divide-slate-100">
                <DetailRow label="Fecha boletín" value={p.bocmDate} />
                <DetailRow label="Artículo" value={p.artNum} mono />
                <DetailRow label="Fuente" value={`${p.sourceLabel} (${p.sourceId})`} />
                <DetailRow label="Municipio" value={p.municipio} />
                <DetailRow label="Sector" value={p.nombreSector} />
                <DetailRow label="Estado trámite" value={p.estadoTramitacion} />
                <DetailRow label="Fecha acuerdo" value={p.fechaAcuerdo} />
                <DetailRow label="Órgano" value={p.organo} />
                <DetailRow label="Promotor" value={p.promotor} />
                <DetailRow
                  label="Viviendas"
                  value={p.numViviendas != null ? String(p.numViviendas) : null}
                />
                <DetailRow
                  label="Superficie total"
                  value={
                    p.supTotalM2 != null ? `${p.supTotalM2.toLocaleString("es-ES")} m²` : null
                  }
                />
                <DetailRow label="ID" value={p.id} mono />
                {categorias.length > 0 ? (
                  <div className="py-3">
                    <dt className="text-xs font-medium uppercase text-slate-500">Categorías</dt>
                    <dd className="mt-2 flex flex-wrap gap-1">
                      {categorias.map((c) => (
                        <span
                          key={c}
                          className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                        >
                          {c}
                        </span>
                      ))}
                    </dd>
                  </div>
                ) : null}
              </dl>
            )}

            {activeTab === "relacionados" && (p.sigmaBoletinMismaExpediente?.length ?? 0) > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Mismo expediente en el BOCM</h2>
                <p className="mt-1 mb-4 text-sm text-slate-500">
                  Otros anuncios donde aparece el mismo número de expediente.
                </p>
                <RelatedBoletines rows={p.sigmaBoletinMismaExpediente!} />
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
