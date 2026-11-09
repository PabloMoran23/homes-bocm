import { NextResponse } from "next/server";
import { loadProjectById } from "@/lib/load-project";
import { loadSigmaFichaBySlug } from "@/lib/load-sigma-ficha";
import { loadProyectoInfoExtra } from "@/lib/load-proyecto-info-extra";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";
import { proyectoTituloPublico } from "@/lib/proyecto-info-extra";
import type { AreaProjectDetail } from "@/lib/area-context";

export const maxDuration = 30;
export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id")?.trim() || "";
  if (!id || id.length > 220 || !/^[\w:./-]+$/.test(id)) return NextResponse.json({ error: "Proyecto no válido" }, { status: 400 });
  try {
    // Use exactly the loaders of /proyecto/[id], not a second project database.
    const project = await loadProjectById(id);
    const ficha = project ? null : await loadSigmaFichaBySlug(id);
    if (!project && !ficha) return NextResponse.json({ error: "No se encontró la ficha del proyecto" }, { status: 404 });
    const group = project?.sigmaExpediente || ficha?.expedienteGrupo || "";
    const [info, metric] = await Promise.all([
      loadProyectoInfoExtra(id, project?.id, group),
      group ? getSigmaMetricForGrupo(group) : Promise.resolve(null),
    ]);
    const detail: AreaProjectDetail = {
      title: proyectoTituloPublico(info) || project?.nombreSector || ficha?.catalog?.EXP_TX_DENOM || project?.title || group,
      summary: info?.resumen || project?.resumen || ficha?.resumenContenido || "",
      phase: project?.sigmaFase || project?.estadoTramitacion || ficha?.catalog?.FAS_TX_DENOM || "Fase no disponible",
      group, info, metric,
      sourceUrl: project?.sigmaVisorUrl || ficha?.visorUrl || project?.sigmaEnlace || ficha?.catalog?.Enlace || project?.pdfUrl || null,
      tramites: project?.sigmaVisorTramitacion || ficha?.tramitacion || [],
      visor: ficha?.visorFicha || null,
      documents: project?.sigmaVisorNtiDocumentosMuestra || ficha?.ntiDocumentosMuestra || [],
      documentsTotal: project?.sigmaVisorNtiDocumentosTotal ?? ficha?.ntiDocumentosTotal ?? null,
      documentsUrl: project?.sigmaVisorNtiListadoUrl || ficha?.ntiListadoUrl || null,
    };
    return NextResponse.json(detail, { headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600" } });
  } catch {
    return NextResponse.json({ error: "No se pudo cargar la ficha. Puedes abrir el proyecto completo o volver a intentarlo." }, { status: 503 });
  }
}
