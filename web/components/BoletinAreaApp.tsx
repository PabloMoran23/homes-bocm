"use client";


import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  BOLETIN_DEFAULT_MONTHS,
  BOLETIN_DEFAULT_RADIUS_M,
  MONTHS_OPTIONS,
  RADIUS_OPTIONS,
  type BoletinAreaResult,
} from "@/lib/boletin-area";
import { NationalAreaExperience } from "@/components/area/NationalAreaExperience";
import type { NationalAreaResult } from "@/lib/national-area";
import { AreaExperience } from "@/components/area/AreaExperience";
import { AddressAutocomplete } from "@/components/AddressAutocomplete";
import { isMadridLocation, isSpainLocation, type AddressLocation } from "@/lib/address-search";
import type { UbicacionSearchItem } from "@/lib/ubicacion";
import { trackEvent } from "@/lib/analytics";

type GeocodeResult = AddressLocation & {
  rawLabel?: string;
  error?: string;
};

function formatEdicionDate(d = new Date()) {
  return d.toLocaleDateString("es-ES", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function BoletinAreaApp({ view = "search" }: { view?: "search" | "results" }) {
  const resultsView = view === "results";
  const router = useRouter();
  const searchParams = useSearchParams();
  const ndpFromUrl = searchParams.get("ndp")?.trim() || null;
  const qFromUrl = searchParams.get("q")?.trim() || null;
  const urlRadius = RADIUS_OPTIONS.some(opt => opt.m === Number(searchParams.get("radiusM"))) ? Number(searchParams.get("radiusM")) : BOLETIN_DEFAULT_RADIUS_M;
  const urlMonths = MONTHS_OPTIONS.some(opt => opt.months === Number(searchParams.get("months"))) ? Number(searchParams.get("months")) : BOLETIN_DEFAULT_MONTHS;
  const queryKey = `${qFromUrl}:${urlRadius}:${urlMonths}`;
  const ndpKey = `${ndpFromUrl}:${urlRadius}:${urlMonths}`;
  const autoLoadedNdp = useRef<string | null>(null);
  const appliedQFromUrl = useRef<string | null>(null);

  const activeSearch = useRef<AbortController | null>(null);
  const initialLocation = { lat:Number(searchParams.get("lat")), lng:Number(searchParams.get("lng")), label:qFromUrl || "", municipality:searchParams.get("localidad") || undefined };
  const geocoded = useRef<{ query: string; result: GeocodeResult } | null>(qFromUrl && searchParams.get("lat") && searchParams.get("lng") && isSpainLocation(initialLocation) ? {query:qFromUrl,result:initialLocation} : null);
  const [q, setQ] = useState(qFromUrl || "");
  const [selected, setSelected] = useState<UbicacionSearchItem | null>(null);
  const [radiusM, setRadiusM] = useState(urlRadius);
  const [months, setMonths] = useState(urlMonths);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nationalData, setNationalData] = useState<NationalAreaResult | null>(null);
  const [data, setData] = useState<BoletinAreaResult | null>(null);

  useEffect(() => () => activeSearch.current?.abort(), []);

  const buscar = useCallback(
    async (override?: { ndp?: string; q?: string; geo?: GeocodeResult }) => {
      const ndp = override?.ndp ?? (override?.q ? undefined : selected?.ndp);
      const freeText = (override?.q ?? q).trim();
      if (!ndp && freeText.length < 3) {
        setError("Escribe una dirección o elige una sugerencia");
        return;
      }
      activeSearch.current?.abort();
      const controller = new AbortController();
      activeSearch.current = controller;
      const timeout = window.setTimeout(() => controller.abort("timeout"), 20_000);
      setLoading(true);
      setError(null);
      setData(null);
      setNationalData(null);
      try {
        const params = new URLSearchParams({
          radiusM: String(resultsView ? urlRadius : radiusM),
          months: String(resultsView ? urlMonths : months),
        });
        if (ndp) {
          params.set("ndp", ndp);
          if (!resultsView) { router.push(`/boletin/resultados?${params}`); return; }
        } else {
          let geo = override?.geo ?? (geocoded.current?.query === freeText ? geocoded.current.result : null);
          if (!geo) {
            const geoRes = await fetch(`/api/geocode-address?q=${encodeURIComponent(freeText)}`, {
              signal: controller.signal,
            });
            geo = await geoRes.json() as GeocodeResult;
            if (!geoRes.ok || geo.error) {
              throw new Error(geo.error || "No se pudo localizar esa dirección");
            }
          }
          if (controller.signal.aborted) return;
          geocoded.current = { query: geo.label, result: geo };
          if (!isSpainLocation(geo)) throw new Error("Elige una dirección en España");
          if (!resultsView) {
            params.set("q", geo.label); params.set("lat", String(geo.lat)); params.set("lng", String(geo.lng));
            if (geo.municipality) params.set("localidad", geo.municipality);
            router.push(`/boletin/resultados?${params}`); return;
          }
          const isMadrid = isMadridLocation(geo) && (!geo.municipality || geo.municipality.toLocaleLowerCase("es") === "madrid");
          if (!isMadrid) {
            if (!geo.municipality) throw new Error("Añade el municipio a la dirección para consultar su información");
            params.set("lat", String(geo.lat)); params.set("lng", String(geo.lng));
            params.set("municipality", geo.municipality); params.set("label", geo.label);
            const response = await fetch(`/api/boletin-area/national?${params}`, { signal: controller.signal });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "No se pudo consultar el municipio");
            if (controller.signal.aborted) return;
            setQ(geo.label); setSelected(null); setNationalData(result);
            trackEvent("boletin_buscar", { modo:"municipio", radius_m:radiusM, months, resultados:result.total });
            return;
          }
          params.set("lat", String(geo.lat));
          params.set("lng", String(geo.lng));
          params.set("label", geo.label);
          setQ(geo.label);
          setSelected(null);
        }
        const res = await fetch(`/api/boletin-area?${params}`, { signal: controller.signal });
        const json = (await res.json()) as BoletinAreaResult & { error?: string };
        if (!res.ok || json.error) {
          throw new Error(json.error || "No se pudo cargar el boletín");
        }
        if (controller.signal.aborted) return;
        if (ndp) {
          const label = json.center.direccion || ndp;
          setQ(label);
          setSelected({ ndp, label, direccion: label, distrito: json.center.distrito || "", barrio: json.center.barrio || "" });
        }
        setData(json);
        trackEvent("boletin_buscar", {
          modo: ndp ? "ndp" : "geocode",
          radius_m: radiusM,
          months,
          distrito: json.center.distrito || "",
          barrio: json.center.barrio || "",
          resultados: json.licencias.length + json.expedientesSigma.length,
        });
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "Error al consultar");
        } else if (controller.signal.reason === "timeout") {
          setError("La consulta está tardando demasiado. Vuelve a intentarlo.");
        }
      } finally {
        window.clearTimeout(timeout);
        if (activeSearch.current === controller) setLoading(false);
      }
    },
    [selected, q, radiusM, months, resultsView, router, urlRadius, urlMonths],
  );

  useEffect(() => {
    if (!resultsView || !qFromUrl || appliedQFromUrl.current === queryKey || ndpFromUrl) return;
    appliedQFromUrl.current = queryKey;
    queueMicrotask(() => {
      setRadiusM(urlRadius); setMonths(urlMonths);
      setQ(qFromUrl);
      setSelected(null);
      const lat = searchParams.get("lat");
      const lng = searchParams.get("lng");
      const location = { lat: Number(lat), lng: Number(lng), label: qFromUrl, municipality: searchParams.get("localidad") || undefined };
      void buscar({ q: qFromUrl, geo: lat && lng && isSpainLocation(location) ? location : undefined });
    });
  }, [qFromUrl, ndpFromUrl, searchParams, buscar, resultsView, queryKey, urlRadius, urlMonths]);

  useEffect(() => {
    if (!resultsView || !ndpFromUrl || autoLoadedNdp.current === ndpKey) return;
    autoLoadedNdp.current = ndpKey;
    queueMicrotask(() => {
      setSelected(null);
      setRadiusM(urlRadius); setMonths(urlMonths);
      setQ(ndpFromUrl);
      void buscar({ ndp: ndpFromUrl });
    });
  }, [ndpFromUrl, buscar, resultsView, ndpKey, urlRadius, urlMonths]);

  const canSearch = !loading && (selected != null || q.trim().length >= 3);
  const filtersStale = Boolean(
    (data && (data.params.radiusM !== radiusM || data.params.months !== months)) || (nationalData && (nationalData.radiusM !== radiusM || nationalData.months !== months)),
  );
  const heavyQuery = radiusM >= 800 && months >= 36;
  const backParams = new URLSearchParams(searchParams.toString()); backParams.set("edit", "1");
  if (!backParams.get("q") && data?.center.direccion) backParams.set("q",data.center.direccion);
  const searchHref = `/boletin?${backParams}`;
  const applyFilters = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("edit"); params.set("radiusM", String(radiusM)); params.set("months", String(months));
    router.push(`/boletin/resultados?${params}`);
  };


  return (
    <div className="min-h-[calc(100dvh-3.5rem)] bg-[#f8f6f1]">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
        {/* Cabecera boletín */}
        {!resultsView && <header className="border-b border-slate-300/60 pb-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--portal-warm)]">
              Tu zona · Explora una dirección
            </p>
            <p className="text-xs text-slate-500 capitalize">{formatEdicionDate()}</p>
          </div>
          <h1 className="mt-3 font-serif text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Entiende lo que pasa en tu zona
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-slate-600">
            Proyectos, cambios recientes y contexto urbanístico alrededor de una dirección.
            Descubre qué se plantea y qué ha cambiado cerca de ti o en tu municipio, según la información disponible.
          </p>
        </header>}

        {resultsView && <nav aria-label="Ruta de navegación" className="mb-6 flex flex-wrap items-center gap-2 text-xs text-slate-500"><Link href="/" className="hover:underline">Inicio</Link><span aria-hidden="true">/</span><Link href={searchHref} className="font-medium text-[var(--portal-accent)] hover:underline">Tu zona</Link><span aria-hidden="true">/</span><span aria-current="page" className="line-clamp-1 max-w-xl">{qFromUrl || data?.center.direccion || "Resultado de la consulta"}</span><Link href={searchHref} className="ml-auto font-medium text-[var(--portal-accent)] hover:underline">← Volver a buscar</Link></nav>}
        {/* Búsqueda */}
        <section aria-label={resultsView ? "Filtros de la consulta" : "Buscar una zona"} className={resultsView ? "mb-6 rounded-xl border border-slate-200/80 bg-white/80 px-4 py-3" : "mt-8 rounded-xl border border-slate-200/80 bg-white/90 p-4 shadow-sm backdrop-blur-sm sm:p-5"}>
          {!resultsView && <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tu dirección</p>
              <AddressAutocomplete
                value={q}
                onChange={value => {
                  activeSearch.current?.abort();
                  setLoading(false);
                  setData(null);
                  setNationalData(null);
                  setError(null);
                  setQ(value);
                  setSelected(null);
                  geocoded.current = null;
                }}
                onSelect={location => {
                  activeSearch.current?.abort();
                  setLoading(false);
                  setData(null);
                  setNationalData(null);
                  setError(null);
                  setQ(location.label);
                  setSelected(null);
                  geocoded.current = { query: location.label, result: location };
                }}
                onSubmit={() => { if (canSearch) void buscar(); }}
              />
            </div>

            <button
              type="button"
              onClick={() => void buscar()}
              disabled={!canSearch}
              className="h-[42px] shrink-0 rounded-lg bg-[var(--portal-accent)] px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--portal-accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Buscando…" : selected ? "Buscar" : "Buscar dirección"}
            </button>
          </div>}

          <div className={resultsView ? "flex flex-wrap gap-x-8 gap-y-3" : "mt-4 flex flex-wrap gap-6 border-t border-slate-100 pt-4"}>
            <fieldset className="space-y-1.5">
              <legend className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Radio de consulta
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

          {heavyQuery && !data ? (
            <p className="mt-3 text-xs text-slate-500">
              Radio amplio y periodo largo: la consulta puede tardar unos segundos.
            </p>
          ) : null}

          {filtersStale ? (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--portal-accent)]/20 bg-[var(--portal-accent-soft)]/80 px-3 py-2.5">
              <p className="text-sm text-[var(--portal-ink)]">
                Has cambiado el radio o el periodo. Pulsa «Actualizar» para actualizar la lectura del entorno.
              </p>
              <button
                type="button"
                onClick={applyFilters}
                disabled={loading}
                className="shrink-0 rounded-lg bg-[var(--portal-accent)] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--portal-accent-hover)] disabled:opacity-50"
              >
                {loading ? "Actualizando…" : "Actualizar entorno"}
              </button>
            </div>
          ) : null}

          {error ? (
            <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {error}
            </p>
          ) : null}
        </section>

        {resultsView && (nationalData ? (
          <div className="scroll-mt-20"><NationalAreaExperience key={`${nationalData.center.lat}:${nationalData.center.lng}:${nationalData.radiusM}:${nationalData.months}`} data={nationalData} /></div>
        ) : data ? (
          <div className="scroll-mt-20">
            <AreaExperience key={`${data.center.lat}:${data.center.lng}:${data.params.radiusM}:${data.params.months}`} data={data} />
          </div>
        ) : (
          <div className="mt-12 rounded-2xl border border-dashed border-slate-300 bg-white/50 px-6 py-16 text-center">
            <p className="font-serif text-lg text-slate-600">{loading ? "Consultando la información de esta zona…" : error ? "No se ha podido completar la consulta." : "Preparando los resultados…"}</p>{error && <button type="button" className="area-text-link mt-4" onClick={() => { void buscar({ ndp: ndpFromUrl || undefined, q: qFromUrl || undefined }); }}>Reintentar consulta</button>}
          </div>
        ))}
      </div>
    </div>
  );
}
