"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  DetailBreadcrumbLink,
} from "@/components/detail/DetailPageShell";
import { KpiTile, SigmaMetricsPanel } from "@/components/detail/SigmaMetricsCards";
import { NtiDocumentList } from "@/components/project-detail/NtiDocumentList";
import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import { SigmaProjectHero } from "@/components/sigma/SigmaProjectHero";
import { SigmaUserResumen } from "@/components/sigma/SigmaUserResumen";
import { SigmaVisorFichaPanel } from "@/components/sigma/SigmaVisorFichaPanel";
import { projectPath } from "@/lib/project-display";
import type { SigmaPresentationInput } from "@/lib/sigma-presentation";
import { sigmaPickDisplayHeadline } from "@/lib/sigma-presentation";
import { fetchSigmaGeoForExpediente } from "@/lib/load-sigma-geo";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import {
  bocmAnunciosTabLabel,
  sigmaFaseLabel,
  SIGMA_BOCM_SECTION_INTRO,
  SIGMA_DOCUMENTOS_INTRO,
  SIGMA_DOCUMENTOS_TAB_LABEL,
  SIGMA_TRAMITACION_INTRO,
} from "@/lib/sigma-user-labels";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
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
      <div className="flex h-52 items-center justify-center rounded-xl bg-slate-100 text-sm text-slate-500">
        Mapa…
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
    ...(tramCount > 0 ? [{ id: "tramitacion" as const, label: "Tramitación" }] : []),
    ...(docTotal > 0 || (ficha.documentacionUrls?.length ?? 0) > 0
      ? [{ id: "documentos" as const, label: SIGMA_DOCUMENTOS_TAB_LABEL }]
      : []),
    ...(hasBocm ? [{ id: "bocm" as const, label: bocmAnunciosTabLabel(ficha.bocmProyectos.length) }] : []),
  ];
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id ?? "resumen";

  const resumenFields = {
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

  const faseLabel = sigmaFaseLabel(c?.FAS_TX_DENOM);
  const vf = ficha.visorFicha;
  const supVisor =
    vf?.superficieAmbitoM2 != null && vf.superficieAmbitoM2 > 0
      ? `${vf.superficieAmbitoM2.toLocaleString("es-ES")} m²`
      : vf?.superficieAmbitoTexto;

  return (
    <main className="mx-auto max-w-[90rem] flex-1 px-4 py-4 sm:px-6 sm:py-5">
      <nav className="mb-3 flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <DetailBreadcrumbLink href="/explore">Mapa Madrid</DetailBreadcrumbLink>
        <span className="text-slate-300">/</span>
        <span className="truncate text-slate-700">{breadcrumbTitle}</span>
      </nav>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(300px,400px)] xl:gap-5 lg:items-start">
        {/* Columna izquierda: presentación + pestañas */}
        <div className="flex min-w-0 flex-col gap-3">
          <SigmaProjectHero
            presentation={presentation}
            visorUrl={visorUrl}
            bocmFirstId={hasBocm ? ficha.bocmProyectos[0].id : null}
            bocmCount={ficha.bocmProyectos.length}
            compact
          />

          {ficha.visorFicha ? (
            <SigmaVisorFichaPanel ficha={ficha.visorFicha} compact showFullText={false} />
          ) : null}

          <div className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-100/80 p-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  activeTab === t.id ? "bg-white text-teal-900 shadow-sm" : "text-slate-600"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <section className="min-h-0 flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="max-h-[min(42vh,380px)] overflow-y-auto p-4 sm:p-5">
              {activeTab === "resumen" && (
                <div className="space-y-4">
                  <SigmaUserResumen
                    fields={resumenFields}
                    visorFicha={ficha.visorFicha}
                    tramitacion={ficha.tramitacion}
                    onVerTramitacion={tramCount > 0 ? () => setTab("tramitacion") : undefined}
                    compact
                  />
                </div>
              )}
              {activeTab === "tramitacion" && tramCount > 0 && (
                <div>
                  <p className="mb-4 text-sm text-slate-600">{SIGMA_TRAMITACION_INTRO}</p>
                  <TramitacionTimeline rows={ficha.tramitacion} />
                </div>
              )}
              {activeTab === "documentos" && (
                <div>
                  <p className="mb-4 text-sm text-slate-600">{SIGMA_DOCUMENTOS_INTRO}</p>
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
                  <p className="mb-4 text-sm text-slate-600">{SIGMA_BOCM_SECTION_INTRO}</p>
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
          </section>
        </div>

        {/* Columna derecha: mapa + métricas */}
        <aside className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-[4.25rem] lg:self-start">
          {sigmaGeo ? (
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <p className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
                Dónde afecta
              </p>
              <ProjectsMap
                points={[]}
                sectorGeoJson={sigmaGeo}
                variant="detail"
                heightClassName="h-[min(calc(100vh-11rem),400px)] min-h-[240px]"
                sectorCountLabel="polígono"
              />
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
              Sin geometría en mapa
            </div>
          )}

          <SigmaMetricsPanel metric={metricProp ?? null} compact />

          <div className="grid grid-cols-2 gap-2">
            {faseLabel ? <KpiTile label="Estado" value={faseLabel} /> : null}
            {vf?.promotor ? (
              <KpiTile label="Promotor" value={vf.promotor} sub={vf.iniciativa ?? undefined} />
            ) : null}
            {supVisor ? <KpiTile label="Superficie" value={supVisor} /> : null}
            {vf?.distrito ? <KpiTile label="Distrito" value={vf.distrito} /> : null}
            {lastTram?.fecha ? (
              <KpiTile
                label="Último hito"
                value={lastTram.fecha}
                sub={lastTram.tramite?.slice(0, 40) || undefined}
              />
            ) : null}
            {docTotal > 0 ? (
              <KpiTile
                label="Documentos"
                value={String(docTotal)}
                sub={ntiLinked?.stats.downloaded ? `${ntiLinked.stats.downloaded} descargados` : undefined}
              />
            ) : null}
          </div>
        </aside>
      </div>

      <p className="mt-6 text-center text-xs text-slate-400">
        Fuente: Ayuntamiento de Madrid ·{" "}
        <Link href={sigmaFichaPath(ficha.expedienteGrupo)} className="hover:text-slate-600">
          enlace permanente
        </Link>
      </p>
    </main>
  );
}