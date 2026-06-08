"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

const BENEFITS = [
  {
    title: "Licencias en edificios cercanos",
    detail: "Obras, cambios de uso y actuaciones en un radio de 300 m a 1,2 km.",
  },
  {
    title: "Proyectos que afectan el entorno",
    detail: "Expedientes de planeamiento con geometría cerca de tu parcela.",
  },
  {
    title: "Lectura en minutos",
    detail: "Cronología clara con distancias y enlaces a cada ficha.",
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
        Ejemplo · 600 m · 24 meses
      </p>
      <p className="mt-2 font-semibold text-slate-900">Calle Mayor, 12 — Centro</p>
      <p className="mt-1 text-sm text-slate-600">
        En los últimos 24 meses, en 600 m a la redonda:{" "}
        <span className="font-medium text-slate-800">4 licencias</span> y{" "}
        <span className="font-medium text-slate-800">2 proyectos</span> de planeamiento.
      </p>
      <ul className="mt-4 space-y-3 border-t border-slate-100 pt-4 text-sm">
        <li className="flex gap-3">
          <span className="mt-0.5 shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-900">
            Licencia
          </span>
          <span className="text-slate-700">Rehabilitación · a 120 m</span>
        </li>
        <li className="flex gap-3">
          <span className="mt-0.5 shrink-0 rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-sky-800">
            Proyecto
          </span>
          <span className="text-slate-700">Ámbito de reforma · te afecta directamente</span>
        </li>
      </ul>
      <div className="mt-4 flex h-28 items-center justify-center rounded-xl border border-dashed border-teal-200/80 bg-gradient-to-br from-teal-50/90 to-white text-xs text-slate-500">
        Mapa del radio y eventos en el boletín
      </div>
    </div>
  );
}

export function LandingTuZonaSection({ isPublic = true }: { isPublic?: boolean }) {
  const router = useRouter();
  const [address, setAddress] = useState("");

  function goToBoletin(e?: FormEvent) {
    e?.preventDefault();
    const q = address.trim();
    router.push(q ? `/boletin?q=${encodeURIComponent(q)}` : "/boletin");
  }

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
              ¿Qué ocurre alrededor de{" "}
              <span className="text-[var(--portal-accent)]">tu dirección</span>?
            </h2>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-slate-600">
              {isPublic ? (
                <>
                  Introduce una calle en Madrid capital y genera un boletín con licencias recientes y
                  proyectos de planeamiento en tu entorno — sin registrarte.
                </>
              ) : (
                <>
                  Genera un boletín personalizado con lo que se tramita cerca de ti: licencias,
                  planeamiento y distancias en un solo informe.
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

            <form className="mt-8 space-y-3" onSubmit={goToBoletin}>
              <label className="block">
                <span className="sr-only">Tu dirección en Madrid</span>
                <input
                  type="text"
                  name="address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="Ej. Calle Gran Vía 28, Madrid"
                  autoComplete="street-address"
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
                />
              </label>
              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  className="inline-flex flex-1 items-center justify-center rounded-xl bg-[var(--portal-accent)] px-5 py-3.5 text-sm font-semibold text-white shadow-md shadow-teal-900/10 transition hover:bg-[var(--portal-accent-hover)] sm:flex-none sm:px-8"
                >
                  Ver boletín de mi zona
                </button>
                <Link
                  href="/boletin"
                  className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-5 py-3.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
                >
                  Abrir sin dirección
                </Link>
              </div>
            </form>
          </div>

          <PreviewCard />
        </div>
      </div>
    </section>
  );
}
