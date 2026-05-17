"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { normSearch } from "@/lib/madrid";
import { LicenciaMapLegend } from "@/components/map/LicenciaMapLegend";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import type { MadridLicenciaRow, MadridLicenciasIndex } from "@/lib/types";

const ProjectsMap = dynamic(
  () => import("./ProjectsMap").then((m) => ({ default: m.ProjectsMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[min(36vh,380px)] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
        Cargando mapa…
      </div>
    ),
  },
);

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{value}</p>
    </div>
  );
}

function parseConcesionYear(fecha: string | null | undefined): number | null {
  if (!fecha) return null;
  const parts = fecha.trim().split(/[/.-]/);
  if (parts.length < 3) return null;
  const y = Number(parts[parts.length - 1]);
  return Number.isFinite(y) ? y : null;
}

export function MadridLicenciasExplorer() {
  const [index, setIndex] = useState<MadridLicenciasIndex | null>(null);
  const [year, setYear] = useState<number | null>(null);
  const [rows, setRows] = useState<MadridLicenciaRow[]>([]);
  const [geo, setGeo] = useState<SectorFeatureCollection | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [uso, setUso] = useState("");
  const [distrito, setDistrito] = useState("");
  const [procedimiento, setProcedimiento] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/data/madrid-licencias-index.json");
        if (!res.ok) throw new Error(String(res.status));
        const json = (await res.json()) as MadridLicenciasIndex;
        if (!cancelled) {
          setIndex(json);
          const defaultYear = json.years?.[0] ?? null;
          setYear(defaultYear);
        }
      } catch {
        if (!cancelled) {
          setErr(
            "No se pudo cargar el índice de licencias. Ejecuta: python3 -m sector_geometry.madrid_licencias_download && npm run build-data",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (year == null) return;
    const ac = new AbortController();
    setLoading(true);
    setErr(null);
    (async () => {
      try {
        const [rowsRes, geoRes] = await Promise.all([
          fetch(`/data/madrid-licencias-${year}.json`, { signal: ac.signal }),
          fetch(`/data/madrid-licencias-${year}.geojson`, { signal: ac.signal }),
        ]);
        if (!rowsRes.ok) throw new Error(`tabla ${rowsRes.status}`);
        const rowData = (await rowsRes.json()) as MadridLicenciaRow[];
        if (!ac.signal.aborted) setRows(rowData);
        if (geoRes.ok && !ac.signal.aborted) {
          setGeo((await geoRes.json()) as SectorFeatureCollection);
        } else if (!ac.signal.aborted) {
          setGeo(null);
        }
      } catch (e) {
        if (!ac.signal.aborted) {
          setErr(e instanceof Error ? e.message : String(e));
          setRows([]);
          setGeo(null);
        }
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    })();
    return () => ac.abort();
  }, [year]);

  const filtered = useMemo(() => {
    const nq = normSearch(q.trim());
    const nu = normSearch(uso);
    const nd = normSearch(distrito);
    const np = normSearch(procedimiento);
    return rows.filter((r) => {
      if (nu && normSearch(r.uso || "") !== nu && !normSearch(r.uso || "").includes(nu)) return false;
      if (nd && normSearch(r.distrito || "") !== nd && !normSearch(r.distrito || "").includes(nd))
        return false;
      if (
        np &&
        normSearch(r.procedimiento || "") !== np &&
        !normSearch(r.procedimiento || "").includes(np)
      )
        return false;
      if (!nq) return true;
      const hay =
        normSearch(r.direccion || "").includes(nq) ||
        normSearch(r.tipoExpediente || "").includes(nq) ||
        normSearch(r.interesado || "").includes(nq) ||
        normSearch(r.objeto || "").includes(nq) ||
        normSearch(r.barrio || "").includes(nq);
      return hay;
    });
  }, [rows, q, uso, distrito, procedimiento]);

  const geoFiltered = useMemo(() => {
    if (!geo?.features?.length || !filtered.length) return geo;
    const allowed = new Set(
      filtered.filter((r) => r.lat != null && r.lng != null).map((r) => `${r.lng},${r.lat}`),
    );
    if (!q.trim() && !uso && !distrito && !procedimiento) return geo;
    return {
      type: "FeatureCollection" as const,
      features: geo.features.filter((f) => {
        const c = f.geometry?.coordinates;
        if (!Array.isArray(c) || c.length < 2) return false;
        return allowed.has(`${c[0]},${c[1]}`);
      }),
    };
  }, [geo, filtered, q, uso, distrito, procedimiento]);

  if (err && !index) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {err}
      </div>
    );
  }

  if (!index) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-200" />
          ))}
        </div>
      </div>
    );
  }

  const yearCount = year != null ? index.byYear[String(year)] ?? rows.length : 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Total (2015–2026)" value={index.totalRows.toLocaleString("es-ES")} />
        <Stat label="Con ubicación" value={index.withCoords.toLocaleString("es-ES")} />
        <Stat
          label={`Año ${year ?? "—"}`}
          value={yearCount.toLocaleString("es-ES")}
        />
        <Stat label="En mapa (año)" value={(geo?.features?.length ?? 0).toLocaleString("es-ES")} />
      </div>

      <p className="text-xs text-slate-500">
        Fuente:{" "}
        <a
          href="https://datos.madrid.es/dataset/300193-0-licencias-urbanisticas"
          className="text-[var(--portal-accent)] hover:underline"
          target="_blank"
          rel="noopener noreferrer"
        >
          datos abiertos Ayto. Madrid (300193)
        </a>
        {index.generatedAt
          ? ` · índice ${new Date(index.generatedAt).toLocaleString("es-ES")}`
          : null}
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[120px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Año</span>
          <select
            value={year ?? ""}
            onChange={(e) => setYear(Number(e.target.value))}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            {index.years.map((y) => (
              <option key={y} value={y}>
                {y} ({(index.byYear[String(y)] ?? 0).toLocaleString("es-ES")})
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-[200px] flex-1 space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Buscar</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Dirección, tipo, promotor, objeto…"
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-[var(--portal-accent)]"
          />
        </label>
        <label className="min-w-[140px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Uso</span>
          <select
            value={uso}
            onChange={(e) => setUso(e.target.value)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            <option value="">Todos</option>
            {index.topUso.map((u) => (
              <option key={u.name} value={u.name}>
                {u.name} ({u.count.toLocaleString("es-ES")})
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-[140px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Distrito</span>
          <select
            value={distrito}
            onChange={(e) => setDistrito(e.target.value)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            <option value="">Todos</option>
            {index.topDistrito.map((d) => (
              <option key={d.name} value={d.name}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-[160px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Procedimiento
          </span>
          <select
            value={procedimiento}
            onChange={(e) => setProcedimiento(e.target.value)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            <option value="">Todos</option>
            {index.topProcedimiento.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name.length > 36 ? `${p.name.slice(0, 34)}…` : p.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <p className="text-sm text-slate-600">
        <span className="font-semibold text-slate-900">{filtered.length.toLocaleString("es-ES")}</span>{" "}
        licencias
        {filtered.length !== rows.length ? (
          <span className="text-slate-500"> de {rows.length.toLocaleString("es-ES")} en {year}</span>
        ) : null}
        {loading ? <span className="ml-2 text-xs text-slate-400">Cargando…</span> : null}
      </p>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-800">Mapa de licencias ({year})</h2>
        {geoFiltered && geoFiltered.features.length > 0 ? (
          <>
            <ProjectsMap
              points={[]}
              sectorGeoJson={geoFiltered}
              dataScope="full"
              variant="detail"
              sectorCountLabel="licencias con ubicación"
              heightClassName="h-[min(42vh,480px)]"
            />
            <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2.5">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Iconos por tipo
              </p>
              <LicenciaMapLegend className="text-[11px] text-slate-600" />
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Cada punto es una licencia con coordenadas (UTM → WGS84). Cada año se carga por separado.
            </p>
          </>
        ) : (
          <p className="text-sm text-slate-500">
            {loading
              ? "Cargando geometrías…"
              : "Sin puntos en mapa para este filtro (muchas filas carecen de coordenadas válidas)."}
          </p>
        )}
      </div>

      <div className="overflow-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[900px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Concesión</th>
              <th className="px-3 py-2">Dirección</th>
              <th className="px-3 py-2">Tipo</th>
              <th className="px-3 py-2">Uso</th>
              <th className="px-3 py-2">Distrito</th>
              <th className="px-3 py-2">Procedimiento</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.slice(0, 400).map((r, i) => (
              <tr key={`${r.ndpEdificio}-${r.fechaConcesion}-${i}`} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-3 py-2 text-slate-700">
                  {r.fechaConcesion || "—"}
                  {parseConcesionYear(r.fechaConcesion) != null ? (
                    <span className="ml-1 text-xs text-slate-400">
                      ({parseConcesionYear(r.fechaConcesion)})
                    </span>
                  ) : null}
                </td>
                <td className="max-w-xs px-3 py-2 text-slate-800">{r.direccion || "—"}</td>
                <td className="max-w-xs px-3 py-2 text-xs text-slate-600">
                  {(r.tipoExpediente || "—").slice(0, 80)}
                </td>
                <td className="px-3 py-2 text-slate-600">{r.uso || "—"}</td>
                <td className="px-3 py-2 text-slate-600">{r.distrito || "—"}</td>
                <td className="max-w-[12rem] px-3 py-2 text-xs text-slate-500">
                  {(r.procedimiento || "—").slice(0, 60)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 400 ? (
          <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
            Mostrando 400 de {filtered.length.toLocaleString("es-ES")}. Afina filtros.
          </p>
        ) : null}
      </div>
    </div>
  );
}
