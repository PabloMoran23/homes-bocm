"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  DetailBreadcrumbLink,
  DetailPageShell,
} from "@/components/detail/DetailPageShell";
import { KpiTile, SigmaMetricsPanel } from "@/components/detail/SigmaMetricsCards";
import { NtiDocumentList } from "@/components/project-detail/NtiDocumentList";
import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import {
  formatSigmaArcgisMs,
  hasValue,
  projectPath,
  sigmaCatalogSourceLabel,
  sigmaLayerKindLabel,
} from "@/lib/project-display";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
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
  const denom = ficha.visorCabecera?.h1 || c?.EXP_TX_DENOM || ficha.expedienteGrupo;
  const sub = ficha.visorCabecera?.h2 || c?.FIG_TX_ETIQ || null;
  const tramCount = ficha.tramitacion.length;
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
    let cancelled = false;
    (async () => {
      const kind = c?.sigma_layer_kind || c?.source;
      const url =
        kind === "tramitados_ad"
          ? "/data/madrid-sigma-ad.geojson"
          : kind === "tramitados_gestion"
            ? "/data/madrid-sigma-gestion.geojson"
            : kind === "tramitados_urbanizacion"
              ? "/data/madrid-sigma-urbanizacion.geojson"
              : "/data/madrid-sigma-ip.geojson";
      try {
        const res = await fetch(url);
        if (!res.ok) return;
        const fc = (await res.json()) as SectorFeatureCollection;
        const exp = ficha.expedienteGrupo;
        const feats = fc.features.filter((f) => {
          const n = String((f.properties as Record<string, unknown>)?.EXP_TX_NUMERO || "");
          return n.includes(exp.split("/").slice(-1)[0] || exp);
        });
        if (!cancelled && feats.length) {
          setSigmaGeo({ type: "FeatureCollection", features: feats });
        }
      } catch {
        /* opcional */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [c?.sigma_layer_kind, c?.source, ficha.expedienteGrupo]);

  const tabs: { id: TabId; label: string }[] = [
    { id: "resumen", label: "Resumen" },
    ...(tramCount > 0 ? [{ id: "tramitacion" as const, label: "Tramitación" }] : []),
    ...(docTotal > 0 || (ficha.documentacionUrls?.length ?? 0) > 0
      ? [{ id: "documentos" as const, label: "Documentos" }]
      : []),
    ...(hasBocm ? [{ id: "bocm" as const, label: `BOCM (${ficha.bocmProyectos.length})` }] : []),
  ];
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id ?? "resumen";

  const hero = (
    <header className="portal-hero-bg overflow-hidden rounded-2xl border border-teal-200/50 shadow-sm">
      <div className="p-5 sm:p-7">
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full bg-teal-100 px-3 py-0.5 text-xs font-semibold text-teal-900">
            Expediente SIGMA
          </span>
          {c?.source === "informacion_publica" ? (
            <span className="rounded-full bg-violet-100 px-3 py-0.5 text-xs font-semibold text-violet-900">
              Información pública
            </span>
          ) : (
            <span className="rounded-full bg-amber-50 px-3 py-0.5 text-xs font-semibold text-amber-900 ring-1 ring-amber-200">
              Catálogo tramitados
            </span>
          )}
          {hasBocm ? (
            <span className="rounded-full bg-sky-50 px-3 py-0.5 text-xs font-semibold text-sky-900 ring-1 ring-sky-200">
              {ficha.bocmProyectos.length} BOCM
            </span>
          ) : null}
        </div>
        <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{denom}</h1>
        {sub ? <p className="mt-1 text-base text-slate-600">{sub}</p> : null}
        <p className="mt-2 font-mono text-sm text-teal-900">{ficha.expedienteGrupo}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {visorUrl ? (
            <a
              href={visorUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex rounded-lg bg-[var(--portal-accent)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--portal-accent-hover)]"
            >
              Visor municipal ↗
            </a>
          ) : null}
          {hasBocm ? (
            <Link
              href={projectPath(ficha.bocmProyectos[0].id)}
              className="inline-flex rounded-lg border border-teal-300 bg-white px-4 py-2 text-sm font-semibold text-teal-950 hover:bg-teal-50"
            >
              Ficha BOCM
            </Link>
          ) : null}
        </div>
      </div>
    </header>
  );

  const aside = (
    <>
      <SigmaMetricsPanel metric={metricProp ?? null} />
      <div className="grid grid-cols-2 gap-2">
        {c?.FAS_TX_DENOM ? <KpiTile label="Fase" value={c.FAS_TX_DENOM} /> : null}
        {lastTram?.fecha ? (
          <KpiTile
            label="Último hito"
            value={lastTram.fecha}
            sub={lastTram.tramite?.slice(0, 48) || undefined}
          />
        ) : null}
        {docTotal > 0 ? (
          <KpiTile label="Docs NTI" value={String(docTotal)} sub={ntiLinked ? `${ntiLinked.stats.downloaded} local` : undefined} />
        ) : null}
      </div>
      {sigmaGeo ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 shadow-sm">
          <p className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
            Ámbito en mapa
          </p>
          <ProjectsMap
            points={[]}
            sectorGeoJson={sigmaGeo}
            variant="detail"
            heightClassName="h-48"
            sectorCountLabel="polígono"
          />
        </div>
      ) : null}
    </>
  );

  return (
    <DetailPageShell
      breadcrumb={
        <>
          <DetailBreadcrumbLink href="/explore">Mapa Madrid</DetailBreadcrumbLink>
          <span className="text-slate-300">/</span>
          <span className="font-mono text-slate-700">{ficha.expedienteGrupo}</span>
        </>
      }
      hero={hero}
      aside={aside}
      footer={
        <p className="text-center text-xs text-slate-400">
          <Link href={sigmaFichaPath(ficha.expedienteGrupo)} className="font-mono hover:text-slate-600">
            {sigmaFichaPath(ficha.expedienteGrupo)}
          </Link>
        </p>
      }
    >
      <div className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-100/80 p-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition ${
              activeTab === t.id ? "bg-white text-teal-900 shadow-sm" : "text-slate-600"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        {activeTab === "resumen" && (
          <dl className="grid gap-4 sm:grid-cols-2">
            <SummaryCell label="Expediente" value={ficha.expedienteGrupo} mono />
            <SummaryCell label="Denominación" value={c?.EXP_TX_DENOM} />
            <SummaryCell label="Fase" value={c?.FAS_TX_DENOM} />
            <SummaryCell label="Figura" value={c?.TFIG_TX_ABREV || c?.FIG_TX_ETIQ} />
            <SummaryCell label="Órgano" value={c?.ORG_TX_DESC} />
            <SummaryCell label="Aprobación" value={formatSigmaArcgisMs(c?.FEX_DT_APROB) ?? undefined} />
            <SummaryCell label="Origen" value={sigmaCatalogSourceLabel(c?.source) ?? undefined} />
            <SummaryCell label="Capa" value={sigmaLayerKindLabel(c?.sigma_layer_kind ?? null) ?? undefined} />
          </dl>
        )}
        {activeTab === "tramitacion" && tramCount > 0 && (
          <TramitacionTimeline rows={ficha.tramitacion} />
        )}
        {activeTab === "documentos" && (
          <NtiDocumentList
            linked={ntiLinked}
            muestra={ficha.ntiDocumentosMuestra}
            totalVisor={ficha.ntiDocumentosTotal}
            listadoUrl={ficha.ntiListadoUrl}
          />
        )}
        {activeTab === "bocm" && hasBocm && (
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
                  BOCM {b.bocmDate}
                  {b.artNum ? ` · art. ${b.artNum}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </DetailPageShell>
  );
}

function SummaryCell({
  label,
  value,
  mono,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  if (!hasValue(value)) return null;
  return (
    <div className="rounded-lg bg-slate-50/80 px-3 py-2.5">
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`mt-1 text-sm text-slate-900 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}
