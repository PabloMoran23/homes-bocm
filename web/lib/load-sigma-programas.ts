import { fetchStaticJson } from "@/lib/fetch-static-json";
import {
  agruparExpedientesPorPrograma,
  type MadridSigmaProgramasFile,
  type SigmaPrograma,
} from "@/lib/sigma-programa";

let programasPromise: Promise<MadridSigmaProgramasFile | null> | null = null;

async function loadProgramasFile(): Promise<MadridSigmaProgramasFile | null> {
  if (!programasPromise) {
    programasPromise = fetchStaticJson<MadridSigmaProgramasFile>("/data/madrid-sigma-programas.json");
  }
  return programasPromise;
}

export async function getSigmaProgramasFile(): Promise<MadridSigmaProgramasFile | null> {
  return loadProgramasFile();
}

export async function getSigmaProgramaForGrupo(
  expedienteGrupo: string,
): Promise<{ programa: SigmaPrograma; ref: NonNullable<MadridSigmaProgramasFile["byExpediente"]>[string] } | null> {
  const file = await loadProgramasFile();
  const ref = file?.byExpediente?.[expedienteGrupo];
  if (!ref?.programaId) return null;
  const programa = file?.byPrograma?.[ref.programaId];
  if (!programa) return null;
  return { programa, ref };
}

export async function getSigmaProgramasForExpedientes(
  expedienteGrupos: string[],
): Promise<{ programas: SigmaPrograma[]; sueltos: string[]; file: MadridSigmaProgramasFile | null }> {
  const file = await loadProgramasFile();
  const { programas, sueltos } = agruparExpedientesPorPrograma(expedienteGrupos, file);
  return { programas, sueltos, file };
}
