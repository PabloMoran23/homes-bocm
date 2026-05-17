import type { Metadata } from "next";
import { ActivateTierButton } from "@/components/ActivateTierButton";
import { TIER_FEATURES, TIER_LABEL, type TierId } from "@/lib/tiers";

export const metadata: Metadata = {
  title: "Planes",
  description:
    "Gratis, Particular y Empresa: profundidad de lectura, alertas y exportación para seguir proyectos urbanísticos con Homes.",
};

const order: TierId[] = ["free", "particular", "empresa"];

const tierHint: Record<TierId, string> = {
  free: "Descubrimiento y uso ocasional",
  particular: "Seguimiento por municipio o compra de vivienda",
  empresa: "Equipos, exportación e integración",
};

export default function PlanesPage() {
  return (
    <main className="mx-auto max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <header className="mb-10 max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Planes</h1>
        <p className="mt-3 text-slate-600">
          Elige cuánta profundidad necesitas para seguir proyectos y estudiar zonas. El selector en la
          cabecera es hoy una{" "}
          <strong className="font-semibold text-slate-800">simulación local</strong> (localStorage +
          cookie) para ensayar límites hasta que activemos cobro e identificación de usuario.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        {order.map((id) => (
          <article
            key={id}
            className={`flex flex-col rounded-2xl border p-6 shadow-sm ${
              id === "particular"
                ? "border-teal-200 bg-gradient-to-b from-[var(--portal-accent-soft)]/90 to-white ring-2 ring-teal-600/20"
                : "border-slate-200 bg-white"
            }`}
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--portal-accent)]">
              {tierHint[id]}
            </p>
            <h2 className="mt-2 text-xl font-semibold text-slate-900">{TIER_LABEL[id]}</h2>
            <ul className="mt-4 flex-1 space-y-2.5 text-sm text-slate-600">
              {TIER_FEATURES[id].map((f) => (
                <li key={f} className="flex gap-2">
                  <span className="mt-0.5 text-[var(--portal-accent)]" aria-hidden>
                    ✓
                  </span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <ActivateTierButton
              tier={id}
              className={`mt-6 w-full rounded-lg py-2.5 text-sm font-semibold transition ${
                id === "particular"
                  ? "bg-[var(--portal-accent)] text-white hover:bg-[var(--portal-accent-hover)]"
                  : "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
              }`}
            >
              Probar plan en explorador
            </ActivateTierButton>
          </article>
        ))}
      </div>

      <section className="mt-14 rounded-xl border border-slate-200 bg-slate-50/80 p-6 text-sm text-slate-600">
        <h3 className="font-semibold text-slate-900">Resumen de límites técnicos (MVP)</h3>
        <ul className="mt-3 list-inside list-disc space-y-1 marker:text-[var(--portal-accent)]">
          <li>
            <strong className="text-slate-800">Gratis</strong>: hasta 60 filas en tabla, resumen
            acortado en la ficha, rankings de estadísticas recortados.
          </li>
          <li>
            <strong className="text-slate-800">Particular</strong>: hasta 400 filas, ficha completa,
            estadísticas completas.
          </li>
          <li>
            <strong className="text-slate-800">Empresa</strong>: exportación CSV del filtrado actual,
            tabla sin tope práctico en el dataset actual.
          </li>
        </ul>
      </section>
    </main>
  );
}
