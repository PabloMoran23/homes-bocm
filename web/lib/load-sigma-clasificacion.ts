import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { SigmaClassification } from "@/lib/sigma-classification";
import type { MadridSigmaClasificacionFile, SigmaMapClassificationRow } from "@/lib/sigma-classification-filters";

let clasificacionPromise: Promise<MadridSigmaClasificacionFile | null> | null = null;

function mapClassificationRow(row: SigmaMapClassificationRow | null | undefined): SigmaClassification | null {
  if (!row?.categoriaProyecto && !row?.tipoObra) return null;
  return {
    tipoLegal: row.tipoLegal,
    escala: row.escala,
    contenidoPrincipal: row.contenidoPrincipal,
    faseNormalizada: row.faseNormalizada,
    categoriaProyecto: row.categoriaProyecto,
    tipoObra: row.tipoObra,
    confianza: row.confianza ?? null,
  };
}

async function loadClasificacionFile(): Promise<MadridSigmaClasificacionFile | null> {
  if (!clasificacionPromise) {
    clasificacionPromise = fetchStaticJson<MadridSigmaClasificacionFile>(
      "/data/madrid-sigma-clasificacion.json",
    );
  }
  return clasificacionPromise;
}

export async function getSigmaClasificacionForGrupos(
  expedienteGrupos: string[],
): Promise<Record<string, SigmaClassification | null>> {
  const file = await loadClasificacionFile();
  const out: Record<string, SigmaClassification | null> = {};
  for (const g of expedienteGrupos) {
    out[g] = mapClassificationRow(file?.byExpediente?.[g]);
  }
  return out;
}

export async function getSigmaClasificacionForGrupo(
  expedienteGrupo: string,
): Promise<SigmaClassification | null> {
  const file = await loadClasificacionFile();
  return mapClassificationRow(file?.byExpediente?.[expedienteGrupo]);
}
