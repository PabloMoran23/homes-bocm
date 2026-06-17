import { loadProjectById } from "@/lib/load-project";
import { loadSigmaFichaBySlug } from "@/lib/load-sigma-ficha";
import { normalizeResumenContenido } from "@/lib/normalize-resumen-contenido";
import { projectHeadline } from "@/lib/project-display";
import { sigmaPickDisplayHeadline } from "@/lib/sigma-presentation";
import { sigmaFaseShortLabel } from "@/lib/sigma-user-labels";

function trimTitle(title: string, max = 72): string {
  return title.length > max ? `${title.slice(0, max - 1)}…` : title;
}

/** Título visible en metadata y breadcrumbs JSON-LD de `/proyecto/[id]`. */
export async function getProyectoPageTitle(id: string): Promise<string | null> {
  const project = await loadProjectById(id);
  if (project) {
    return trimTitle(projectHeadline(project));
  }

  const ficha = await loadSigmaFichaBySlug(id);
  if (!ficha) return null;

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
  return trimTitle(title);
}

export async function getProyectoPageDescription(id: string): Promise<string | undefined> {
  const project = await loadProjectById(id);
  if (project) {
    return project.resumen?.slice(0, 160) || undefined;
  }

  const ficha = await loadSigmaFichaBySlug(id);
  if (!ficha) return undefined;

  const resumen = normalizeResumenContenido(ficha.resumenContenido);
  if (resumen) {
    return resumen.length > 160 ? `${resumen.slice(0, 157).trim()}…` : resumen;
  }
  return ["Proyecto urbanístico en Madrid", sigmaFaseShortLabel(ficha.catalog?.FAS_TX_DENOM)]
    .filter(Boolean)
    .join(" · ");
}
