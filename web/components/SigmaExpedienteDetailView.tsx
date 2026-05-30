"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DetailBreadcrumbLink } from "@/components/detail/DetailPageShell";
import { SigmaMetricsPanel } from "@/components/detail/SigmaMetricsCards";
import { NtiDocumentList } from "@/components/project-detail/NtiDocumentList";
import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import { SigmaProjectHero } from "@/components/sigma/SigmaProjectHero";
import { SigmaAtAGlance } from "@/components/sigma/SigmaAtAGlance";
import { SigmaClassificationSummary } from "@/components/sigma/SigmaClassificationSummary";
import { SigmaVisorFichaPanel } from "@/components/sigma/SigmaVisorFichaPanel";
import {
  SigmaInfoPublicaBanner,
  SigmaTechnicalDetails,
  type SigmaResumenFields,
} from "@/components/sigma/SigmaUserResumen";
import { projectPath } from "@/lib/project-display";
import type { SigmaPresentationInput } from "@/lib/sigma-presentation";
import { sigmaPickDisplayHeadline } from "@/lib/sigma-presentation";
import { fetchSigmaGeoForExpediente } from "@/lib/load-sigma-geo";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import {
  bocmAnunciosTabLabel,
  SIGMA_BOCM_SECTION_INTRO,
  SIGMA_DOCUMENTOS_INTRO,
  SIGMA_DOCUMENTOS_TAB_LABEL,
  SIGMA_TRAMITACION_INTRO,
} from "@/lib/sigma-user-labels";
import { type SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import {
  loadSigmaNtiLinkedBundle,
  lookupSigmaNtiGrupo,
  type SigmaNtiLinkedBundle,
} from "@/lib/sigma-nti-linked";
import type { SigmaFicha } from "@/lib/types";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

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

type TabId = "resumen" | "tramitacion" | "documentos" | "bocm";

export function SigmaExpedienteDetailView({
  ficha,
  metric: metricProp,
}: {
  ficha: SigmaFicha;
  metric?: SigmaExpedienteMetric | null;
}) {
  const [ntiBundle, setNtiBundle] = useState<SigmaNtiLinkedBundle | null>(null);
  const [tab, setTab] = useState<TabId>("resumen");
  const [sigmaGeo, setSigmaGeo] = useState<SectorFeatureCollection | null>(null);

  const c = ficha.catalog;
  const tramCount = ficha.tramitacion.length;
  const presentation: SigmaPresentationInput = {
    expedienteGrupo: ficha.expedienteGrupo,
    source: c?.source,
    denominacion: c?.EXP_TX_DENOM,
    visorH1: ficha.visorCabecera?.h1,
    visorH2: ficha.visorCabecera?.h2,
    fase: c?.FAS_TX_DENOM,
    figEtiq: c?.FIG_TX_ETIQ,
    tfigAbrev: c?.TFIG_TX_ABREV,
    organo: c?.ORG_TX_DESC,
    metric: metricProp ?? null,
    tramitacion: ficha.tramitacion,
    bocmCount: ficha.bocmProyectos.length,
    tieneDocumentos:
      Boolean(ficha.ntiListadoUrl) ||
      (ficha.ntiDocumentosTotal ?? 0) > 0 ||
      (ficha.documentacionUrls?.length ?? 0) > 0,
    visorFicha: ficha.visorFicha,
    resumenContenido: ficha.resumenContenido,
  };
  const { title: breadcrumbTitle } = sigmaPickDisplayHeadline(presentation);
  const ntiLinked = useMemo(
    () => lookupSigmaNtiGrupo(ntiBundle, ficha.expedienteGrupo),
    [ntiBundle, ficha.expedienteGrupo],
  );
  const docTotal = ntiLinked?.stats.total ?? ficha.ntiDocumentosTotal ?? 0;
  const hasBocm = ficha.bocmProyectos.length > 0;
  const lastTram = ficha.tramitacion[ficha.tramitacion.length - 1];
  const visorUrl = ficha.visorUrl || c?.Enlace || null;

  useEffect(() => {
    let cancelled = false;
    loadSigmaNtiLinkedBundle().then((b) => {
      if (!cancelled) setNtiBundle(b);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    let cancelled = false;
    (async () => {
      const geo = await fetchSigmaGeoForExpediente(ficha.expedienteGrupo, {
        layerKind: c?.sigma_layer_kind,
        source: c?.source,
        signal: ac.signal,
      });
      if (!cancelled) setSigmaGeo(geo);
    })();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [c?.sigma_layer_kind, c?.source, ficha.expedienteGrupo]);

  const tabs: { id: TabId; label: string }[] = [
    { id: "resumen", label: "Resumen" },
    ...(tramCount > 0 ? [{ id: "tramitacion" as const, label: "Cronología" }] : []),
    ...(docTotal > 0 || (ficha.documentacionUrls?.length ?? 0) > 0
      ? [{ id: "documentos" as const, label: SIGMA_DOCUMENTOS_TAB_LABEL }]
      : []),
    ...(hasBocm ? [{ id: "bocm" as const, label: bocmAnunciosTabLabel(ficha.bocmProyectos.length) }] : []),
  ];
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id ?? "resumen";

  const resumenFields: SigmaResumenFields = {
    expedienteGrupo: ficha.expedienteGrupo,
    denominacion: c?.EXP_TX_DENOM,
    fase: c?.FAS_TX_DENOM,
    figEtiq: c?.FIG_TX_ETIQ,
    tfigAbrev: c?.TFIG_TX_ABREV,
    organo: c?.ORG_TX_DESC,
    aprobacionMs: c?.FEX_DT_APROB,
    infopubIniMs: c?.FEX_DT_INFOPUB_INI,
    infopubFinMs: c?.FEX_DT_INFOPUB_FIN,
    source: c?.source,
    layerKind: c?.sigma_layer_kind,
  };

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 overflow-x-hidden px-4 py-6 sm:px-6 sm:py-8">
      <nav className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <DetailBreadcrumbLink href="/explore">Mapa Madrid</DetailBreadcrumbLink>
        <span className="text-slate-300">/</span>
        <span className="truncate text-slate-700">{breadcrumbTitle}</span>
      </nav>

      <SigmaProjectHero
        presentation={presentation}
        clasificacion={ficha.clasificacion}
        visorUrl={visorUrl}
        bocmFirstId={hasBocm ? ficha.bocmProyectos[0].id : null}
        bocmCount={ficha.bocmProyectos.length}
      />

      <div className="mt-8 grid w-full min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <aside className="min-w-0 space-y-5 lg:sticky lg:top-6 lg:self-start">
          {sigmaGeo ? (
            <div className="overflow-hidden rounded-xl border border-indigo-200/80 bg-white shadow-sm">
              <p className="border-b border-indigo-100 bg-indigo-50/70 px-3 py-2 text-xs font-semibold text-indigo-900">
                Ámbito del proyecto
              </p>
              <ProjectsMap
                points={[]}
                sectorGeoJson={sigmaGeo}
                variant="detail"
                heightClassName="min-h-[220px] h-[min(32vh,320px)]"
                sectorCountLabel="ámbito"
              />
              <p className="border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500">
                Polígono aproximado del planeamiento urbanístico.
              </p>
            </div>
          ) : (
            <div className="flex min-h-[220px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
              Sin geometría en mapa
            </div>
          )}

          {ficha.clasificacion ? (
            <div className="rounded-xl border border-indigo-100 bg-white p-4 shadow-sm">
              <SigmaClassificationSummary value={ficha.clasificacion} compact />
            </div>
          ) : null}

          <SigmaMetricsPanel metric={metricProp ?? null} compact />

          <Link
            href="/explore"
            className="block rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm font-semibold text-[var(--portal-accent)] hover:bg-slate-100"
          >
            Ver en el mapa de Madrid
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
                onClick={() => setTab(t.id)}
                className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition ${
                  activeTab === t.id
                    ? "bg-white text-indigo-950 shadow-sm"
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
                <SigmaAtAGlance
                  presentation={presentation}
                  resumenContenido={ficha.resumenContenido}
                  visorFicha={ficha.visorFicha}
                  metric={metricProp ?? null}
                  lastTramDate={lastTram?.fecha}
                />
                {ficha.visorFicha ? (
                  <SigmaVisorFichaPanel ficha={ficha.visorFicha} compact hideResumen />
                ) : null}
                <SigmaInfoPublicaBanner fields={resumenFields} />
                <SigmaTechnicalDetails
                  fields={resumenFields}
                  visorFicha={ficha.visorFicha}
                  clasificacion={ficha.clasificacion}
                />
              </div>
            )}

            {activeTab === "tramitacion" && tramCount > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Cronología de tramitación</h2>
                <p className="mt-1 mb-4 text-sm text-slate-600">{SIGMA_TRAMITACION_INTRO}</p>
                <TramitacionTimeline rows={ficha.tramitacion} />
              </div>
            )}

            {activeTab === "documentos" && (
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Documentos oficiales</h2>
                <p className="mt-1 mb-4 text-sm text-slate-600">{SIGMA_DOCUMENTOS_INTRO}</p>
                <NtiDocumentList
                  linked={ntiLinked}
                  muestra={ficha.ntiDocumentosMuestra}
                  totalVisor={ficha.ntiDocumentosTotal}
                  listadoUrl={ficha.ntiListadoUrl}
                />
              </div>
            )}

            {activeTab === "bocm" && hasBocm && (
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Anuncios en el Boletín</h2>
                <p className="mt-1 mb-4 text-sm text-slate-600">{SIGMA_BOCM_SECTION_INTRO}</p>
                <ul className="grid gap-3 sm:grid-cols-2">
                  {ficha.bocmProyectos.map((b) => (
                    <li key={b.id} className="rounded-xl border border-slate-100 bg-slate-50/50 p-4">
                      <Link
                        href={projectPath(b.id)}
                        className="font-semibold text-[var(--portal-accent)] hover:underline"
                      >
                        {b.title?.slice(0, 100) || b.id}
                      </Link>
                      <p className="mt-1 text-xs text-slate-500">
                        Boletín {b.bocmDate}
                        {b.artNum ? ` · art. ${b.artNum}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      <p className="mt-8 text-center text-xs text-slate-400">
        Fuente: Ayuntamiento de Madrid ·{" "}
        <Link href={sigmaFichaPath(ficha.expedienteGrupo)} className="hover:text-slate-600">
          enlace permanente
        </Link>
      </p>
    </main>
  );
}
