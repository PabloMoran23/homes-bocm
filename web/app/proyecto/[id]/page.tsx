import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProyectoViewTracker } from "@/components/ProyectoViewTracker";
import { ProjectDetailView } from "@/components/ProjectDetailView";
import { SigmaExpedienteDetailView } from "@/components/SigmaExpedienteDetailView";
import { JsonLd } from "@/components/seo/JsonLd";
import { getSigmaClasificacionForGrupos } from "@/lib/load-sigma-clasificacion";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";
import { getSigmaProgramaForGrupo } from "@/lib/load-sigma-programas";
import { loadProjectById } from "@/lib/load-project";
import { loadProyectoInfoExtra } from "@/lib/load-proyecto-info-extra";
import { loadSigmaFichaBySlug } from "@/lib/load-sigma-ficha";
import { proyectoBreadcrumbJsonLd } from "@/lib/json-ld";
import { getProyectoPageDescription, getProyectoPageTitle } from "@/lib/proyecto-seo";
import type { SigmaPrograma } from "@/lib/sigma-programa";
import { withCanonical } from "@/lib/seo";

type PageProps = {
  params: Promise<{ id: string }>;
};

function proyectoPath(id: string): string {
  return `/proyecto/${encodeURIComponent(id)}`;
}

async function clasificacionProgramaMiembros(programa: SigmaPrograma | null | undefined) {
  if (!programa?.miembros.length) return {};
  return getSigmaClasificacionForGrupos(programa.miembros.map((m) => m.expedienteGrupo));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  const path = proyectoPath(id);
  const title = await getProyectoPageTitle(id);
  if (!title) return withCanonical(path, { title: "Proyecto no encontrado" });

  return withCanonical(path, {
    title,
    description: await getProyectoPageDescription(id),
  });
}

export default async function ProyectoPage({ params }: PageProps) {
  const { id } = await params;
  const pageTitle = await getProyectoPageTitle(id);
  const breadcrumbLd = pageTitle ? proyectoBreadcrumbJsonLd(id, pageTitle) : null;

  const project = await loadProjectById(id);
  if (project) {
    const [programaCtx, infoExtra] = await Promise.all([
      project.sigmaExpediente
        ? getSigmaProgramaForGrupo(String(project.sigmaExpediente))
        : Promise.resolve(null),
      loadProyectoInfoExtra(id, project.id, project.sigmaExpediente),
    ]);
    const clasificacionByExpediente = await clasificacionProgramaMiembros(programaCtx?.programa);
    return (
      <>
        {breadcrumbLd ? <JsonLd data={breadcrumbLd} /> : null}
        <ProyectoViewTracker id={id} kind="bocm" />
        <ProjectDetailView
          project={project}
          programa={programaCtx?.programa ?? null}
          programaRef={programaCtx?.ref ?? null}
          clasificacionByExpediente={clasificacionByExpediente}
          infoExtra={infoExtra}
        />
      </>
    );
  }

  const ficha = await loadSigmaFichaBySlug(id);
  if (!ficha) notFound();

  const [metric, programaCtx, infoExtra] = await Promise.all([
    getSigmaMetricForGrupo(ficha.expedienteGrupo),
    getSigmaProgramaForGrupo(ficha.expedienteGrupo),
    loadProyectoInfoExtra(id, ficha.expedienteGrupo),
  ]);
  const clasificacionByExpediente = await clasificacionProgramaMiembros(programaCtx?.programa);
  return (
    <>
      {breadcrumbLd ? <JsonLd data={breadcrumbLd} /> : null}
      <ProyectoViewTracker id={id} kind="sigma" />
      <SigmaExpedienteDetailView
        ficha={ficha}
        metric={metric}
        programa={programaCtx?.programa ?? null}
        programaRef={programaCtx?.ref ?? null}
        clasificacionByExpediente={clasificacionByExpediente}
        infoExtra={infoExtra}
      />
    </>
  );
}
