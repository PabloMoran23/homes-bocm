import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProyectoViewTracker } from "@/components/ProyectoViewTracker";
import { ProjectDetailView } from "@/components/ProjectDetailView";
import { SigmaExpedienteDetailView } from "@/components/SigmaExpedienteDetailView";
import { loadProjectById } from "@/lib/load-project";
import { loadSigmaFichaBySlug } from "@/lib/load-sigma-ficha";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";
import { normalizeResumenContenido } from "@/lib/normalize-resumen-contenido";
import { projectHeadline } from "@/lib/project-display";
import { sigmaPickDisplayHeadline } from "@/lib/sigma-presentation";
import { sigmaFaseShortLabel } from "@/lib/sigma-user-labels";
import { withCanonical } from "@/lib/seo";

type PageProps = {
  params: Promise<{ id: string }>;
};

function proyectoPath(id: string): string {
  return `/proyecto/${encodeURIComponent(id)}`;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  const path = proyectoPath(id);
  const project = await loadProjectById(id);
  if (project) {
    const title = projectHeadline(project);
    return withCanonical(path, {
      title: title.length > 72 ? `${title.slice(0, 69)}…` : title,
      description: project.resumen?.slice(0, 160) || undefined,
    });
  }

  const ficha = await loadSigmaFichaBySlug(id);
  if (!ficha) return withCanonical(path, { title: "Proyecto no encontrado" });

  const { title } = sigmaPickDisplayHeadline({
    expedienteGrupo: ficha.expedienteGrupo,
    source: ficha.catalog?.source,
    denominacion: ficha.catalog?.EXP_TX_DENOM,
    visorH1: ficha.visorCabecera?.h1,
    visorH2: ficha.visorCabecera?.h2,
    fase: ficha.catalog?.FAS_TX_DENOM,
    figEtiq: ficha.catalog?.FIG_TX_ETIQ,
    tfigAbrev: ficha.catalog?.TFIG_TX_ABREV,
    organo: ficha.catalog?.ORG_TX_DESC,
  });
  return withCanonical(path, {
    title: title.length > 72 ? `${title.slice(0, 69)}…` : title,
    description: (() => {
      const resumen = normalizeResumenContenido(ficha.resumenContenido);
      if (resumen) {
        return resumen.length > 160 ? `${resumen.slice(0, 157).trim()}…` : resumen;
      }
      return ["Proyecto urbanístico en Madrid", sigmaFaseShortLabel(ficha.catalog?.FAS_TX_DENOM)]
        .filter(Boolean)
        .join(" · ");
    })(),
  });
}

export default async function ProyectoPage({ params }: PageProps) {
  const { id } = await params;
  const project = await loadProjectById(id);
  if (project) {
    return (
      <>
        <ProyectoViewTracker id={id} kind="bocm" />
        <ProjectDetailView project={project} />
      </>
    );
  }

  const ficha = await loadSigmaFichaBySlug(id);
  if (!ficha) notFound();

  const metric = await getSigmaMetricForGrupo(ficha.expedienteGrupo);
  return (
    <>
      <ProyectoViewTracker id={id} kind="sigma" />
      <SigmaExpedienteDetailView ficha={ficha} metric={metric} />
    </>
  );
}
