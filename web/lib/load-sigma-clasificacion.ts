import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { SigmaClassification } from "@/lib/sigma-classification";
import type { MadridSigmaClasificacionFile, SigmaMapClassificationRow } from "@/lib/sigma-classification-filters";
import { getSupabaseServer } from "@/lib/supabase/server";

let clasificacionPromise: Promise<MadridSigmaClasificacionFile | null> | null = null;
let dominioIndexPromise: Promise<Record<string, SigmaMapClassificationRow> | null> | null = null;

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

async function loadClasificacionFromSupabase(): Promise<Record<string, SigmaMapClassificationRow> | null> {
  if (!dominioIndexPromise) {
    dominioIndexPromise = (async () => {
      const supabase = getSupabaseServer();
      if (!supabase) return null;
      const { data, error } = await supabase.rpc("list_sigma_clasificacion");
      if (error) {
        console.warn("list_sigma_clasificacion:", error.message);
        return null;
      }
      return (data ?? {}) as Record<string, SigmaMapClassificationRow>;
    })();
  }
  return dominioIndexPromise;
}

async function loadClasificacionFile(): Promise<MadridSigmaClasificacionFile | null> {
  if (!clasificacionPromise) {
    clasificacionPromise = fetchStaticJson<MadridSigmaClasificacionFile>(
      "/data/madrid-sigma-clasificacion.json",
    );
  }
  return clasificacionPromise;
}

async function rowForGrupo(expedienteGrupo: string): Promise<SigmaMapClassificationRow | null | undefined> {
  const dominio = await loadClasificacionFromSupabase();
  if (dominio && expedienteGrupo in dominio) {
    return dominio[expedienteGrupo];
  }
  const file = await loadClasificacionFile();
  return file?.byExpediente?.[expedienteGrupo];
}

export async function getSigmaClasificacionForGrupos(
  expedienteGrupos: string[],
): Promise<Record<string, SigmaClassification | null>> {
  const dominio = await loadClasificacionFromSupabase();
  const file = dominio ? null : await loadClasificacionFile();
  const out: Record<string, SigmaClassification | null> = {};
  for (const g of expedienteGrupos) {
    const row = dominio?.[g] ?? file?.byExpediente?.[g];
    out[g] = mapClassificationRow(row);
  }
  return out;
}

export async function getSigmaClasificacionForGrupo(
  expedienteGrupo: string,
): Promise<SigmaClassification | null> {
  return mapClassificationRow(await rowForGrupo(expedienteGrupo));
}
