import { SeguirProyectoProvider } from "@/components/seguir-proyecto/SeguirProyecto";
import { ExploreAreaBanner } from "@/components/project-detail/ExploreAreaBanner";
import { firstPlaceName, resolveSeguirOferta } from "@/lib/seguir-proyecto";
import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import {
  ProjectTerritoryNavigation,
  RelatedDirectoryProjects,
} from "@/components/directory/DirectoryNavigation";
import {
  directoryProjectPath,
  getDirectoryProject,
  projectTerritory,
  type DirectoryProject,
} from "@/lib/project-directory";
import { ProyectoViewTracker } from "@/components/ProyectoViewTracker";
import { ProjectDetailView } from "@/components/ProjectDetailView";
import { SigmaExpedienteDetailView } from "@/components/SigmaExpedienteDetailView";
import { JsonLd } from "@/components/seo/JsonLd";
import { getSigmaClasificacionForGrupo, getSigmaClasificacionForGrupos } from "@/lib/load-sigma-clasificacion";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";
import { getSigmaProgramaForGrupo } from "@/lib/load-sigma-programas";
import { loadProjectById } from "@/lib/load-project";
import { loadProyectoInfoExtra } from "@/lib/load-proyecto-info-extra";
import { loadSigmaFichaBySlug } from "@/lib/load-sigma-ficha";
import { proyectoBreadcrumbJsonLd } from "@/lib/json-ld";
import {
  getProyectoPageDescription,
  getProyectoPageTitle,
} from "@/lib/proyecto-seo";
import type { SigmaPrograma } from "@/lib/sigma-programa";
import { withCanonical } from "@/lib/seo";

type PageProps = {
  params: Promise<{ id: string }>;
};

export const revalidate = 600;

// Ids are not known at build. An empty list still opts the segment into ISR
// fallback (dynamicParams stays true). Without this, Next treats the route as
// fully dynamic and sends private, no-store on every request.
export function generateStaticParams() {
  return [];
}

export const dynamicParams = true;

async function projectId(params: PageProps["params"]): Promise<string> {
  const { id } = await params;
  // Next can supply encoded IDs to the page and decoded IDs to metadata.
  // Use the same key for BOCM identifiers containing a colon in both paths.
  try {
    return decodeURIComponent(id);
  } catch {
    notFound();
  }
}

function municipioDirectorio(project: DirectoryProject | undefined): string | null {
  if (!project) return null;
  try {
    return projectTerritory(project).municipality.name;
  } catch {
    return null;
  }
}

function proyectoPath(id: string): string {
  return `/proyecto/${encodeURIComponent(id)}`;
}

async function clasificacionProgramaMiembros(
  programa: SigmaPrograma | null | undefined,
) {
  if (!programa?.miembros.length) return {};
  return getSigmaClasificacionForGrupos(
    programa.miembros.map((m) => m.expedienteGrupo),
  );
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const id = await projectId(params);
  const directoryProject = getDirectoryProject(id);
  if (directoryProject && directoryProject.id !== id)
    permanentRedirect(directoryProjectPath(directoryProject));
  const path = directoryProject
    ? directoryProjectPath(directoryProject)
    : proyectoPath(id);
  const title = await getProyectoPageTitle(id);
  if (!title) return withCanonical(path, { title: "Proyecto no encontrado" });

  return withCanonical(path, {
    title,
    description: await getProyectoPageDescription(id),
  });
}

export default async function ProyectoPage({ params }: PageProps) {
  const id = await projectId(params);
  const directoryProject = getDirectoryProject(id);
  if (directoryProject && directoryProject.id !== id)
    permanentRedirect(directoryProjectPath(directoryProject));
  const pageTitle = await getProyectoPageTitle(id);
  const breadcrumbLd = pageTitle
    ? proyectoBreadcrumbJsonLd(id, pageTitle)
    : null;

  const project = await loadProjectById(id);
  if (project) {
    const [programaCtx, infoExtra, clasificacionPropia] = await Promise.all([
      project.sigmaExpediente
        ? getSigmaProgramaForGrupo(String(project.sigmaExpediente))
        : Promise.resolve(null),
      loadProyectoInfoExtra(id, project.id, project.sigmaExpediente),
      project.sigmaExpediente
        ? getSigmaClasificacionForGrupo(String(project.sigmaExpediente))
        : Promise.resolve(null),
    ]);
    const clasificacionByExpediente = await clasificacionProgramaMiembros(
      programaCtx?.programa,
    );
    const municipio = firstPlaceName([
      project.municipio,
      municipioDirectorio(directoryProject),
      project.territorioLabel,
    ]);
    const oferta = resolveSeguirOferta({
      fase: project.sigmaFase,
      faseNormalizada: clasificacionPropia?.faseNormalizada,
      estado: project.estadoTramitacion,
      instrumentos: [
        project.tipoInstrumento,
        project.sigmaTipoFigura,
        project.sigmaFiguraCodigo,
        clasificacionPropia?.tipoLegal,
        project.sigmaDenominacion,
        project.title,
        project.sigmaVisorCabecera?.h1,
        project.sigmaVisorCabecera?.h2,
      ],
      ambito: project.nombreSector,
      municipio,
    });
    return (
      <SeguirProyectoProvider projectId={id} municipio={municipio} aviso={oferta.aviso} lugar={oferta.lugar}>
        {directoryProject ? (
          <ProjectTerritoryNavigation project={{ ...directoryProject, title: pageTitle || directoryProject.title }} />
        ) : breadcrumbLd ? (
          <JsonLd data={breadcrumbLd} />
        ) : null}
        <ProyectoViewTracker id={id} kind="bocm" />
        <ProjectDetailView
          hasTerritoryNavigation={Boolean(directoryProject)}
          project={project}
          programa={programaCtx?.programa ?? null}
          programaRef={programaCtx?.ref ?? null}
          clasificacionByExpediente={clasificacionByExpediente}
          infoExtra={infoExtra}
        />
        <div className="mx-auto w-full max-w-6xl px-4 pb-8 sm:px-6"><ExploreAreaBanner /></div>
        {directoryProject ? (
          <RelatedDirectoryProjects project={directoryProject} />
        ) : null}
      </SeguirProyectoProvider>
    );
  }

  const ficha = await loadSigmaFichaBySlug(id);
  if (!ficha) notFound();

  const [metric, programaCtx, infoExtra] = await Promise.all([
    getSigmaMetricForGrupo(ficha.expedienteGrupo),
    getSigmaProgramaForGrupo(ficha.expedienteGrupo),
    loadProyectoInfoExtra(id, ficha.expedienteGrupo),
  ]);
  const clasificacionByExpediente = await clasificacionProgramaMiembros(
    programaCtx?.programa,
  );
  const municipio = firstPlaceName([municipioDirectorio(directoryProject), "Madrid"]);
  const oferta = resolveSeguirOferta({
    fase: ficha.catalog?.FAS_TX_DENOM,
    faseNormalizada: ficha.clasificacion?.faseNormalizada,
    instrumentos: [
      ficha.catalog?.FIG_TX_ETIQ,
      ficha.catalog?.TFIG_TX_ABREV,
      ficha.clasificacion?.tipoLegal,
      ficha.catalog?.EXP_TX_DENOM,
      ficha.visorFicha?.figuraTipo,
      ficha.visorFicha?.tipoPlaneamiento,
      ficha.visorCabecera?.h1,
      ficha.visorCabecera?.h2,
    ],
    distrito: ficha.visorFicha?.distrito,
    ambito: ficha.visorFicha?.ambitoOrdenacion || ficha.visorFicha?.descripcionAmbito,
    municipio,
  });
  return (
    <SeguirProyectoProvider projectId={id} municipio={municipio} aviso={oferta.aviso} lugar={oferta.lugar}>
      {directoryProject ? (
        <ProjectTerritoryNavigation project={{ ...directoryProject, title: pageTitle || directoryProject.title }} />
      ) : breadcrumbLd ? (
        <JsonLd data={breadcrumbLd} />
      ) : null}
      <ProyectoViewTracker id={id} kind="sigma" />
      <SigmaExpedienteDetailView
        hasTerritoryNavigation={Boolean(directoryProject)}
        ficha={ficha}
        metric={metric}
        programa={programaCtx?.programa ?? null}
        programaRef={programaCtx?.ref ?? null}
        clasificacionByExpediente={clasificacionByExpediente}
        infoExtra={infoExtra}
      />
      <div className="mx-auto w-full max-w-6xl px-4 pb-8 sm:px-6"><ExploreAreaBanner /></div>
      {directoryProject ? (
        <RelatedDirectoryProjects project={directoryProject} />
      ) : null}
    </SeguirProyectoProvider>
  );
}
