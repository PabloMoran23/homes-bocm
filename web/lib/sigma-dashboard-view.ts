import type { MadridDashboardStats } from "@/lib/types";
import type { SigmaDashboardView } from "@/lib/sigma-dashboard-filters";

/** Normaliza stats.sigma al shape usado por el dashboard (con ejes de clasificación). */
export function sigmaStatsToView(sig: MadridDashboardStats["sigma"]): SigmaDashboardView {
  return {
    ...sig,
    conClasificacion: sig.conClasificacion ?? 0,
    byCategoriaProyecto: sig.byCategoriaProyecto ?? [],
    byTipoObra: sig.byTipoObra ?? [],
    byTipoLegal: sig.byTipoLegal ?? [],
    byEscala: sig.byEscala ?? [],
    byFaseNormalizada: sig.byFaseNormalizada ?? [],
    byConfianza: sig.byConfianza ?? [],
    bySistemaActuacion: sig.bySistemaActuacion ?? [],
    byUnidadTramitadora: sig.byUnidadTramitadora ?? [],
    byAmbitoOrdenacion: sig.byAmbitoOrdenacion ?? [],
  };
}
