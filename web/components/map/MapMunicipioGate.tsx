"use client";

import { useEffect, useMemo, useState } from "react";
import type { CmMunicipioOption } from "@/lib/cm-portal-geo";
import { MAP_CM_MUNICIPIOS_API } from "@/lib/map-live-urls";

export type MapMunicipioSelection = {
  municipio: CmMunicipioOption;
  from: string;
  to: string;
};

function norm(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function sortMunicipiosByCount(list: CmMunicipioOption[]): CmMunicipioOption[] {
  return [...list].sort((a, b) => b.n - a.n || a.nombre.localeCompare(b.nombre, "es"));
}

export function MapMunicipioGate({
  open,
  initialSlug,
  initialFrom,
  initialTo,
  onConfirm,
}: {
  open: boolean;
  initialSlug?: string | null;
  initialFrom?: string;
  initialTo?: string;
  onConfirm: (selection: MapMunicipioSelection) => void;
}) {
  const [municipios, setMunicipios] = useState<CmMunicipioOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [slug, setSlug] = useState(initialSlug ?? "");
  const [from, setFrom] = useState(initialFrom ?? "");
  const [to, setTo] = useState(initialTo ?? "");

  useEffect(() => {
    if (!open) return;
    setSlug(initialSlug ?? "");
    setFrom(initialFrom ?? "");
    setTo(initialTo ?? "");
  }, [open, initialSlug, initialFrom, initialTo]);

  useEffect(() => {
    if (!open || municipios.length > 0) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const res = await fetch(MAP_CM_MUNICIPIOS_API);
        if (!res.ok) throw new Error("municipios");
        const body = (await res.json()) as { municipios?: CmMunicipioOption[] };
        if (!cancelled) {
          const rows = Array.isArray(body.municipios) ? body.municipios : [];
          setMunicipios(sortMunicipiosByCount(rows));
        }
      } catch {
        if (!cancelled) setLoadErr("No hemos podido cargar la lista de municipios.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, municipios.length]);

  const selected = municipios.find((m) => m.slug === slug) ?? null;
  const matches = useMemo(() => {
    const nq = norm(q.trim());
    const pool = nq
      ? municipios.filter((m) => norm(m.nombre).includes(nq) || norm(m.slug).includes(nq))
      : municipios;
    return nq ? sortMunicipiosByCount(pool).slice(0, 12) : sortMunicipiosByCount(pool);
  }, [municipios, q]);

  if (!open) return null;

  const datesOk = !from || !to || from <= to;

  return (
    <div className="absolute inset-0 z-[1200] flex items-end justify-center bg-slate-900/35 p-4 sm:items-center">
      <form
        className="w-full max-w-md rounded-2xl border border-white/80 bg-white p-5 shadow-xl"
        onSubmit={(e) => {
          e.preventDefault();
          if (!selected || !datesOk) return;
          onConfirm({ municipio: selected, from, to });
        }}
      >
        <h2 className="text-lg font-bold tracking-tight text-slate-900">¿Qué municipio quieres ver?</h2>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">
          Cargamos los proyectos de ese municipio y el mapa se acerca hasta allí.
        </p>

        <label className="mt-4 block space-y-1 text-sm text-slate-700">
          <span className="font-medium">Municipio</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={loading ? "Cargando municipios…" : "Busca un municipio"}
            disabled={loading || Boolean(loadErr)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/20"
            autoComplete="off"
          />
        </label>

        {loadErr ? <p className="mt-2 text-sm text-amber-800">{loadErr}</p> : null}

        {selected ? (
          <p className="mt-2 text-sm text-slate-800">
            <span className="font-semibold">{selected.nombre}</span>
            <span className="text-slate-500">
              {" "}
              · {selected.n.toLocaleString("es-ES")} proyectos en total
            </span>
          </p>
        ) : null}
        <ul className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-slate-100" role="listbox">
          {matches.map((m) => (
            <li key={m.slug}>
              <button
                type="button"
                className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                  m.slug === slug ? "bg-slate-50 font-semibold" : ""
                }`}
                onClick={() => {
                  setSlug(m.slug);
                  setQ("");
                }}
              >
                <span className="font-medium text-slate-900">{m.nombre}</span>
                <span className="shrink-0 text-xs text-slate-500">{m.n.toLocaleString("es-ES")}</span>
              </button>
            </li>
          ))}
          {!loading && matches.length === 0 ? (
            <li className="px-3 py-2 text-sm text-slate-500">Ningún municipio con ese nombre.</li>
          ) : null}
        </ul>

        <div className="mt-4">
          <p className="text-sm font-medium text-slate-700">Última actividad</p>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
            Opcional. Si lo dejas vacío, ves el municipio entero. La fecha es el último movimiento que tenemos, no el inicio del expediente.
          </p>
          <div className="mt-2 grid grid-cols-2 gap-3">
            <label className="block space-y-1 text-sm text-slate-700">
              <span className="font-medium">Desde</span>
              <input
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/20"
              />
            </label>
            <label className="block space-y-1 text-sm text-slate-700">
              <span className="font-medium">Hasta</span>
              <input
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/20"
              />
            </label>
          </div>
        </div>
        {!datesOk ? <p className="mt-1 text-xs text-amber-800">La fecha inicial tiene que ser anterior a la final.</p> : null}

        <button
          type="submit"
          disabled={!selected || !datesOk}
          className="mt-4 w-full rounded-lg bg-[var(--portal-accent)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--portal-accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          Ver en el mapa
        </button>
      </form>
    </div>
  );
}
