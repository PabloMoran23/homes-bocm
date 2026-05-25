import { LICENCIAS_DASHBOARD_NOTA, ORDENANZA_LICENCIAS_2022 } from "@/lib/licencias-actuacion-familias";

export function LicenciasDatosNota() {
  return (
    <div
      className="mb-6 rounded-2xl border border-teal-200/80 bg-teal-50/60 px-4 py-3.5 text-sm leading-relaxed text-slate-700 ring-1 ring-teal-900/[0.04] sm:px-5"
      role="note"
    >
      <p className="font-semibold text-teal-900">Cómo leer estas cifras</p>
      <p className="mt-1.5 text-slate-600">{LICENCIAS_DASHBOARD_NOTA}</p>
      <p className="mt-2 text-xs text-slate-500">
        Referencia: {ORDENANZA_LICENCIAS_2022.label} (vigencia general{" "}
        {ORDENANZA_LICENCIAS_2022.monthKey.replace("-", "/")}).
      </p>
    </div>
  );
}
