export type SigmaProgramaRol = "ordenacion" | "gestion" | "urbanizacion" | "proteccion" | "otro";

export type SigmaProgramaMiembroRef = {
  expedienteGrupo: string;
  rol: SigmaProgramaRol;
  ordenFase: number;
  overlapRatio?: number | null;
  denominacion?: string | null;
  anio?: number | null;
};

export type SigmaPrograma = {
  programaId: string;
  titulo: string;
  ambitoOrdenacion: string | null;
  distrito: string | null;
  anioInicio: number | null;
  anioFin: number | null;
  confianza: "alta" | "media" | "baja";
  metodoAgrupacion: string;
  expedienteLider: string;
  miembrosCount: number;
  miembros: SigmaProgramaMiembroRef[];
};

export type SigmaProgramaExpedienteRef = {
  programaId: string;
  rol: SigmaProgramaRol;
  ordenFase: number;
};

export type MadridSigmaProgramasFile = {
  generatedAt?: string;
  count?: number;
  byExpediente?: Record<string, SigmaProgramaExpedienteRef>;
  byPrograma?: Record<string, SigmaPrograma>;
};

const ROL_LABEL: Record<SigmaProgramaRol, string> = {
  ordenacion: "Ordenación",
  gestion: "Gestión / suelo",
  urbanizacion: "Urbanización / redes",
  proteccion: "Protección / catálogo",
  otro: "Otro trámite",
};

export function sigmaProgramaRolLabel(rol: SigmaProgramaRol | string | null | undefined): string {
  if (!rol) return "Expediente";
  return ROL_LABEL[rol as SigmaProgramaRol] ?? "Expediente";
}

export function agruparExpedientesPorPrograma(
  expedienteGrupos: string[],
  file: MadridSigmaProgramasFile | null,
): {
  programas: SigmaPrograma[];
  sueltos: string[];
} {
  if (!file?.byExpediente || !file.byPrograma) {
    return { programas: [], sueltos: expedienteGrupos };
  }

  const programaIds = new Set<string>();
  const sueltos: string[] = [];

  for (const g of expedienteGrupos) {
    const ref = file.byExpediente[g];
    if (ref?.programaId && file.byPrograma[ref.programaId]) {
      programaIds.add(ref.programaId);
    } else {
      sueltos.push(g);
    }
  }

  const programas = [...programaIds]
    .map((id) => file.byPrograma![id])
    .filter(Boolean)
    .sort((a, b) => (a.anioInicio ?? 9999) - (b.anioInicio ?? 9999));

  return { programas, sueltos };
}
