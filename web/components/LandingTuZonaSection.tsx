"use client";

import { LandingAddressForm } from "@/components/LandingAddressForm";

const BENEFITS = [
  {
    title: "Obras y reformas en edificios de al lado",
    detail: "Permisos de obra, cambios de uso y actuaciones en un radio de 300 m a 1,2 km.",
  },
  {
    title: "Planes que pueden cambiar tu barrio",
    detail: "Tramitaciones con ámbito cerca de tu parcela o edificio.",
  },
  {
    title: "Todo en orden, con distancias y fechas",
    detail: "Cronología clara y enlaces a cada caso.",
  },
] as const;

function PreviewCard() {
  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-teal-200/70 bg-white p-5 shadow-lg shadow-teal-900/5 ring-1 ring-slate-900/[0.04] sm:p-6"
      aria-hidden
    >
      <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-teal-400/15 blur-2xl" />
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--portal-accent)]">
        Ejemplo · 500 m · último año
      </p>
      <p className="mt-2 font-semibold text-slate-900">Calle Mayor, 12 — Centro</p>
      <p className="mt-1 text-sm text-slate-600">
        En el último año, en 500 m a la redonda:{" "}
        <span className="font-medium text-slate-800">4 obras</span> y{" "}
        <span className="font-medium text-slate-800">2 planes</span> en tramitación.
      </p>
      <ul className="mt-4 space-y-3 border-t border-slate-100 pt-4 text-sm">
        <li className="flex gap-3">
          <span className="mt-0.5 shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-900">
            Obra
          </span>
          <span className="text-slate-700">Rehabilitación · a 120 m</span>
        </li>
        <li className="flex gap-3">
          <span className="mt-0.5 shrink-0 rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-sky-800">
            Plan
          </span>
          <span className="text-slate-700">Reforma del barrio · te afecta directamente</span>
        </li>
      </ul>
      <div className="mt-4 flex h-28 items-center justify-center rounded-xl border border-dashed border-teal-200/80 bg-gradient-to-br from-teal-50/90 to-white text-xs text-slate-500">
        Mapa del radio y actividad reciente
      </div>
    </div>
  );
}

export function LandingTuZonaSection({ isPublic = true }: { isPublic?: boolean }) {
  return (
    <section
      className="border-y border-slate-200/80 bg-gradient-to-b from-[#f8f6f1] via-white to-teal-50/40"
      aria-labelledby="landing-tu-zona-heading"
    >
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:items-center lg:gap-12">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--portal-accent)]">
              Tu zona
            </p>
            <h2
              id="landing-tu-zona-heading"
              className="mt-3 text-3xl font-semibold tracking-tight text-[var(--portal-ink)] [text-wrap:balance] sm:text-4xl"
            >
              ¿Qué ha pasado cerca de{" "}
              <span className="text-[var(--portal-accent)]">casa</span>?
            </h2>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-slate-600">
              {isPublic ? (
                <>
                  Pon tu calle en Madrid y te mostramos obras, permisos y planes en un radio a tu
                  alrededor — gratis y sin registrarte.
                </>
              ) : (
                <>
                  Genera un informe con lo que se ha movido cerca de ti: obras, planes y
                  distancias en una sola lectura.
                </>
              )}
            </p>

            <ul className="mt-6 space-y-3">
              {BENEFITS.map((b) => (
                <li key={b.title} className="flex gap-3 text-sm">
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--portal-accent)]"
                    aria-hidden
                  />
                  <span>
                    <span className="font-semibold text-slate-900">{b.title}</span>
                    <span className="text-slate-600"> — {b.detail}</span>
                  </span>
                </li>
              ))}
            </ul>

            <LandingAddressForm />
          </div>

          <PreviewCard />
        </div>
      </div>
    </section>
  );
}
