"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  boletinResumenParrafo,
  MONTHS_OPTIONS,
  RADIUS_OPTIONS,
  type BoletinAreaResult,
  type BoletinEvento,
} from "@/lib/boletin-area";
import { LicenciaTitulo } from "@/components/LicenciaTitulo";
import type { UbicacionSearchItem } from "@/lib/ubicacion";
import { sigmaSlugFromExpediente, ubicacionPath } from "@/lib/ubicacion";
import { fechaRelativaEs } from "@/lib/ubicacion-resumen";

const BoletinMiniMap = dynamic(
  () => import("./BoletinMiniMap").then((m) => ({ default: m.BoletinMiniMap })),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-[min(72vh,680px)] flex-1 animate-pulse rounded-2xl bg-slate-200" />
    ),
  },
);

function norm(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function formatEdicionDate(d = new Date()) {
  return d.toLocaleDateString("es-ES", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function EventoFila({ ev }: { ev: BoletinEvento }) {
  const cuando = fechaRelativaEs(ev.fecha);
  const href =
    ev.tipo === "sigma" && ev.expedienteGrupo
      ? `/sigma/${sigmaSlugFromExpediente(ev.expedienteGrupo)}`
      : ev.ndp
        ? ubicacionPath(ev.ndp)
        : null;

  return (
    <li className="group border-b border-slate-200/80 py-4 last:border-0">
      <div className="flex gap-4">
        <div className="w-20 shrink-0 pt-0.5 text-right">
          <time
            dateTime={cuando.iso ?? undefined}
            title={cuando.title ?? undefined}
            className="block text-xs font-semibold tabular-nums text-[var(--portal-accent)]"
          >
            {cuando.label}
          </time>
          {ev.distanciaM != null ? (
            <span className="mt-1 block text-[10px] text-slate-400">
              {ev.distanciaM === 0 ? "En tu parcela" : `${ev.distanciaM} m`}
            </span>
          ) : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                ev.tipo === "sigma"
                  ? "bg-sky-100 text-sky-800"
                  : "bg-amber-100 text-amber-900"
              }`}
            >
              {ev.tipo === "sigma" ? "Planeamiento" : "Licencia"}
            </span>
            {ev.contienePunto ? (
              <span className="text-[10px] font-medium text-teal-700">Te afecta directamente</span>
            ) : null}
          </div>
          {ev.tipo === "licencia" ? (
            <LicenciaTitulo
              tipoExpediente={ev.titulo}
              className="text-base font-semibold leading-snug text-slate-900"
              notaClassName="mt-1 text-xs text-slate-500"
            />
          ) : (
            <>
              <h3 className="text-base font-semibold leading-snug text-slate-900">{ev.titulo}</h3>
              {ev.detalle ? <p className="mt-1 text-sm text-slate-600">{ev.detalle}</p> : null}
            </>
          )}
          {ev.tipo === "licencia" && ev.detalle ? (
            <p className="mt-1 text-sm text-slate-600">{ev.direccion || ev.detalle}</p>
          ) : null}
          {href ? (
            <Link
              href={href}
              className="mt-2 inline-flex text-xs font-semibold text-[var(--portal-accent)] opacity-80 transition group-hover:opacity-100 hover:underline"
            >
              Leer más →
            </Link>
          ) : null}
        </div>
      </div>
    </li>
  );
}

export function BoletinAreaApp() {
  const [searchIndex, setSearchIndex] = useState<UbicacionSearchItem[]>([]);
  const [searchReady, setSearchReady] = useState(false);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<UbicacionSearchItem | null>(null);
  const [openSuggest, setOpenSuggest] = useState(false);
  const [radiusM, setRadiusM] = useState(600);
  const [months, setMonths] = useState(24);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<BoletinAreaResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/data/ubicaciones-search.json");
        if (!res.ok) throw new Error("missing");
        if (!cancelled) {
          setSearchIndex((await res.json()) as UbicacionSearchItem[]);
          setSearchReady(true);
        }
      } catch {
        if (!cancelled) setError("No hay índice de direcciones. Ejecuta export_ubicaciones_web.py");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const suggestions = useMemo(() => {
    const nq = norm(q.trim());
    if (nq.length < 2) return [];
    return searchIndex
      .filter((item) => {
        const blob = norm(
          [item.label, item.direccion, item.distrito, item.barrio, item.ndp].join(" "),
        );
        return blob.includes(nq);
      })
      .slice(0, 10);
  }, [q, searchIndex]);

  const buscar = useCallback(async () => {
    const ndp = selected?.ndp;
    if (!ndp) {
      setError("Elige una dirección de la lista");
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const params = new URLSearchParams({
        ndp,
        radiusM: String(radiusM),
        months: String(months),
      });
      const res = await fetch(`/api/boletin-area?${params}`);
      const json = (await res.json()) as BoletinAreaResult & { error?: string };
      if (!res.ok || json.error) {
        throw new Error(json.error || "No se pudo cargar el boletín");
      }
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al consultar");
    } finally {
      setLoading(false);
    }
  }, [selected, radiusM, months]);

  const pickSuggestion = useCallback((item: UbicacionSearchItem) => {
    setSelected(item);
    setQ(item.label);
    setOpenSuggest(false);
    setData(null);
    setError(null);
  }, []);

  const radioLabel = RADIUS_OPTIONS.find((o) => o.m === (data?.params.radiusM ?? radiusM))?.label;

  return (
    <div className="min-h-[calc(100dvh-3.5rem)] bg-[#f8f6f1]">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
        {/* Cabecera boletín */}
        <header className="border-b border-slate-300/60 pb-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--portal-warm)]">
              Boletín de tu área
            </p>
            <p className="text-xs text-slate-500 capitalize">{formatEdicionDate()}</p>
          </div>
          <h1 className="mt-3 font-serif text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Qué ha pasado cerca de ti
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-slate-600">
            Tu resumen de licencias y planeamiento en el barrio. Elige dirección y radio; el mapa
            muestra el ámbito que estamos leyendo.
          </p>
        </header>

        {/* Búsqueda */}
        <section className="mt-8 rounded-xl border border-slate-200/80 bg-white/90 p-4 shadow-sm backdrop-blur-sm sm:p-5">
          <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <label className="relative block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Tu dirección
              </span>
              <input
                type="search"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setSelected(null);
                  setOpenSuggest(true);
                }}
                onFocus={() => setOpenSuggest(true)}
                placeholder="Calle, número o barrio…"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-[var(--portal-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--portal-accent-soft)]"
                autoComplete="off"
              />
              {openSuggest && suggestions.length > 0 ? (
                <ul className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
                  {suggestions.map((item) => (
                    <li key={item.ndp}>
                      <button
                        type="button"
                        className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => pickSuggestion(item)}
                      >
                        <span className="font-medium text-slate-900">{item.label}</span>
                        <span className="mt-0.5 block text-xs text-slate-500">
                          {[item.distrito, item.barrio].filter(Boolean).join(" · ")}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </label>

            <button
              type="button"
              onClick={buscar}
              disabled={!searchReady || loading || !selected}
              className="h-[42px] shrink-0 rounded-lg bg-[var(--portal-accent)] px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--portal-accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Buscando…" : "Buscar"}
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-6 border-t border-slate-100 pt-4">
            <fieldset className="space-y-1.5">
              <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Radio del boletín
              </legend>
              <div className="flex flex-wrap gap-1.5">
                {RADIUS_OPTIONS.map((opt) => (
                  <button
                    key={opt.m}
                    type="button"
                    onClick={() => setRadiusM(opt.m)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      radiusM === opt.m
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </fieldset>
            <fieldset className="space-y-1.5">
              <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Periodo
              </legend>
              <div className="flex flex-wrap gap-1.5">
                {MONTHS_OPTIONS.map((opt) => (
                  <button
                    key={opt.months}
                    type="button"
                    onClick={() => setMonths(opt.months)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      months === opt.months
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </fieldset>
          </div>

          {error ? (
            <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {error}
            </p>
          ) : null}
        </section>

        {/* Resultado: boletín + mapa */}
        {data ? (
          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(340px,46%)] lg:items-start xl:gap-10">
            {/* Columna editorial */}
            <article className="min-w-0 rounded-2xl border border-slate-200/80 bg-white px-5 py-6 shadow-sm sm:px-8 sm:py-8">
              <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400">
                Edición local · radio {radioLabel}
              </p>
              <h2 className="mt-2 font-serif text-2xl font-semibold leading-tight text-slate-900 sm:text-3xl">
                {data.center.direccion || selected?.label || "Tu zona"}
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                {[data.center.distrito, data.center.barrio].filter(Boolean).join(" · ")}
                <span className="mx-2 text-slate-300">·</span>
                Últimos {data.params.months} meses
              </p>

              <p className="mt-5 border-l-4 border-[var(--portal-accent)] pl-4 text-lg leading-relaxed text-slate-700">
                {boletinResumenParrafo(data)}
              </p>

              <dl className="mt-6 grid grid-cols-3 gap-3 border-y border-slate-100 py-4">
                <div>
                  <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                    Licencias
                  </dt>
                  <dd className="mt-0.5 font-serif text-2xl font-semibold text-slate-900">
                    {data.stats.licencias}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                    Planeamiento
                  </dt>
                  <dd className="mt-0.5 font-serif text-2xl font-semibold text-slate-900">
                    {data.stats.expedientesSigma}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                    Novedades
                  </dt>
                  <dd className="mt-0.5 font-serif text-2xl font-semibold text-slate-900">
                    {data.stats.eventos}
                  </dd>
                </div>
              </dl>

              {data.center.ndp ? (
                <Link
                  href={ubicacionPath(data.center.ndp)}
                  className="mt-2 inline-flex text-sm font-semibold text-[var(--portal-accent)] hover:underline"
                >
                  Ficha del edificio →
                </Link>
              ) : null}

              <section className="mt-8">
                <h3 className="border-b border-slate-900 pb-2 font-serif text-lg font-semibold text-slate-900">
                  Cronología
                </h3>
                {data.timeline.length === 0 ? (
                  <p className="mt-4 text-sm text-slate-600">
                    No hay actividad reciente con estos filtros. Prueba ampliar el radio o el periodo.
                  </p>
                ) : (
                  <ol className="mt-2 divide-y divide-slate-100">
                    {data.timeline.map((ev, i) => (
                      <EventoFila key={`${ev.tipo}-${ev.titulo}-${i}`} ev={ev} />
                    ))}
                  </ol>
                )}
              </section>

              <footer className="mt-8 border-t border-slate-100 pt-4 text-[11px] leading-relaxed text-slate-400">
                Datos: licencias urbanísticas del Ayuntamiento de Madrid y expedientes SIGMA. Las
                fechas de planeamiento corresponden al último trámite conocido en el visor. No
                indican inicio ni fin de obra salvo que se indique lo contrario.
              </footer>
            </article>

            {/* Mapa sticky derecha */}
            <aside className="w-full min-w-0 lg:sticky lg:top-20 lg:self-start">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Mapa del ámbito · {radioLabel}
              </p>
              <BoletinMiniMap
                key={`map-${data.center.ndp}-${data.params.radiusM}`}
                variant="panel"
                lat={data.center.lat}
                lng={data.center.lng}
                radiusM={data.params.radiusM}
                licencias={data.licencias}
                expedientesSigma={data.expedientesSigma}
              />
            </aside>
          </div>
        ) : (
          <div className="mt-12 rounded-2xl border border-dashed border-slate-300 bg-white/50 px-6 py-16 text-center">
            <p className="font-serif text-lg text-slate-600">
              Introduce tu dirección y pulsa «Generar boletín» para ver el resumen de tu zona.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
