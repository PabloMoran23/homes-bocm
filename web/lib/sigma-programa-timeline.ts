import {
  anioReferenciaMunicipal,
  fechaDestacadaUbicacionExpediente,
  parseFechaEs,
} from "@/lib/ubicacion-resumen";
import type { SigmaProgramaMiembroRef } from "@/lib/sigma-programa";
import type { UbicacionSigmaExpediente, UbicacionTramite } from "@/lib/ubicacion";

export type ProgramaMiembroCronologia = {
  miembro: SigmaProgramaMiembroRef;
  anio: string | null;
  fechaSort: number;
};

export type ProgramaMiembroExpedienteCtx = Pick<
  UbicacionSigmaExpediente,
  "expediente_grupo" | "exp_numero_original" | "fecha_aprob" | "denominacion"
>;

/** Fecha clave + año mostrado para un miembro del programa (tramitación > aprobación > ref. municipal). */
export function cronologiaProgramaMiembro(
  miembro: SigmaProgramaMiembroRef,
  exp?: ProgramaMiembroExpedienteCtx | null,
  tramites: UbicacionTramite[] = [],
): ProgramaMiembroCronologia {
  let fechaSort = 0;
  let anio: string | null = miembro.anio ? String(miembro.anio) : null;

  if (exp) {
    const { fecha, fechaSort: fs, soloAnio } = fechaDestacadaUbicacionExpediente(exp, tramites);
    if (fs > 0) {
      fechaSort = fs;
      if (fecha) {
        if (soloAnio) {
          anio = fecha;
        } else {
          const parsed = parseFechaEs(fecha);
          anio = parsed ? String(parsed.getFullYear()) : anio;
        }
      }
    }
  }

  if (!fechaSort) {
    const refAnio =
      (anio ? Number(anio) : null) ??
      (exp ? anioReferenciaMunicipal(exp) : null) ??
      anioReferenciaMunicipal({ expediente_grupo: miembro.expedienteGrupo, exp_numero_original: null });
    if (refAnio) {
      fechaSort = new Date(refAnio, 0, 1).getTime();
      anio = String(refAnio);
    }
  }

  return { miembro, anio, fechaSort };
}

/** Orden cronológico (antiguo → reciente); empate por fase urbanística y referencia. */
export function ordenarMiembrosProgramaCronologico(
  miembros: SigmaProgramaMiembroRef[],
  ctx: {
    expedientesByGrupo?: Record<string, ProgramaMiembroExpedienteCtx>;
    tramitacionSigma?: Record<string, UbicacionTramite[]>;
  } = {},
): ProgramaMiembroCronologia[] {
  return miembros
    .map((m) =>
      cronologiaProgramaMiembro(
        m,
        ctx.expedientesByGrupo?.[m.expedienteGrupo] ?? null,
        ctx.tramitacionSigma?.[m.expedienteGrupo] ?? [],
      ),
    )
    .sort((a, b) => {
      if (a.fechaSort !== b.fechaSort) {
        if (!a.fechaSort) return 1;
        if (!b.fechaSort) return -1;
        return a.fechaSort - b.fechaSort;
      }
      const fase = a.miembro.ordenFase - b.miembro.ordenFase;
      if (fase !== 0) return fase;
      return (a.miembro.denominacion || a.miembro.expedienteGrupo).localeCompare(
        b.miembro.denominacion || b.miembro.expedienteGrupo,
        "es",
      );
    });
}
