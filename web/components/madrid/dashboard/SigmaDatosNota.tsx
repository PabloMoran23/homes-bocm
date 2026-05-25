import { SIGMA_DASHBOARD_NOTA } from "@/lib/sigma-dashboard-constants";

export function SigmaDatosNota() {
  return (
    <div
      className="mb-6 rounded-2xl border border-violet-200/80 bg-violet-50/50 px-4 py-3.5 text-sm leading-relaxed text-slate-700 ring-1 ring-violet-900/[0.04] sm:px-5"
      role="note"
    >
      <p className="font-semibold text-violet-950">Proyectos urbanísticos y clasificación</p>
      <p className="mt-2 text-xs text-slate-500">
        Los cuatro ejes del clasificador (categoría, tipo de obra, instrumento y escala) se derivan del
        objeto del expediente y de la ficha municipal. Los gráficos de detalle usan los mismos campos
        que ves en cada ficha de proyecto.
      </p>
    </div>
  );
}
