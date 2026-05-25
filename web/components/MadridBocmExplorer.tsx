"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ensureProject } from "@/lib/ensure-project";
import { isMadridCapital, normSearch } from "@/lib/madrid";
import {
  coordSourceLabel,
  projectPath,
  relevanciaBadgeClass,
  relevanciaLabel,
} from "@/lib/project-display";
import type { Project } from "@/lib/types";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import { filterSectorGeoJsonForProjects } from "@/lib/filter-sector-geo";
import type { MapPoint } from "./ProjectsMap";

const ProjectsMap = dynamic(
  () => import("./ProjectsMap").then((m) => ({ default: m.ProjectsMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[min(40vh,420px)] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
        Cargando mapa…
      </div>
    ),
  },
);

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{value}</p>
      {hint ? <p className="mt-0.5 text-[10px] text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function MadridBocmExplorer() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [sectorGeoJson, setSectorGeoJson] = useState<SectorFeatureCollection | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [tipo, setTipo] = useState("");
  const [relevancia, setRelevancia] = useState<"all" | "relevant" | "not_relevant" | "unknown">(
    "all",
  );
  const [sigmaFilter, setSigmaFilter] = useState<"all" | "linked" | "unlinked">("all");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [projRes, geoRes] = await Promise.all([
          fetch("/data/projects.json"),
          fetch("/data/sector-geometries.geojson"),
        ]);
        if (!projRes.ok) throw new Error(String(projRes.status));
        const data = (await projRes.json()) as Partial<Project>[];
        const madrid = data
          .map((row) => ensureProject(row as Partial<Project> & { id: string }))
          .filter((p) => isMadridCapital(p.municipio));
        if (!cancelled) setProjects(madrid);
        if (geoRes.ok && !cancelled) {
          setSectorGeoJson((await geoRes.json()) as SectorFeatureCollection);
        }
      } catch {
        if (!cancelled) setErr("No se pudo cargar BOCM Madrid. Ejecuta npm run build-data.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const tipos = useMemo(() => {
    if (!projects) return [];
    const s = new Set<string>();
    for (const p of projects) {
      s.add(p.tipoInstrumento || "Sin clasificar");
    }
    return [...s].sort((a, b) => a.localeCompare(b, "es"));
  }, [projects]);

  const filtered = useMemo(() => {
    if (!projects) return [];
    const nq = normSearch(q.trim());
    return projects.filter((p) => {
      if (relevancia === "relevant" && p.esRelevante !== true) return false;
      if (relevancia === "not_relevant" && p.esRelevante !== false) return false;
      if (relevancia === "unknown" && p.esRelevante != null) return false;
      if (tipo && (p.tipoInstrumento || "Sin clasificar") !== tipo) return false;
      if (sigmaFilter === "linked" && !p.sigmaExpediente) return false;
      if (sigmaFilter === "unlinked" && p.sigmaExpediente) return false;
      const y = p.bocmDate.slice(0, 4);
      if (yearFrom && y && y < yearFrom) return false;
      if (yearTo && y && y > yearTo) return false;
      if (!nq) return true;
      return (
        normSearch(p.title).includes(nq) ||
        normSearch(p.resumen).includes(nq) ||
        normSearch(p.nombreSector).includes(nq) ||
        normSearch(p.procedimientoExpediente || "").includes(nq) ||
        normSearch(p.sigmaExpediente || "").includes(nq) ||
        normSearch(p.sigmaDenominacion || "").includes(nq)
      );
    });
  }, [projects, q, tipo, relevancia, sigmaFilter, yearFrom, yearTo]);

  const mapPoints: MapPoint[] = useMemo(() => {
    const out: MapPoint[] = [];
    for (const p of filtered) {
      if (p.lat == null || p.lng == null) continue;
      out.push({
        municipio: (p.nombreSector || p.title).slice(0, 40),
        count: 1,
        lat: p.lat,
        lng: p.lng,
      });
    }
    return out;
  }, [filtered]);

  const sectorGeo = useMemo(
    () => filterSectorGeoJsonForProjects(sectorGeoJson, filtered),
    [sectorGeoJson, filtered],
  );

  const stats = useMemo(() => {
    if (!projects) return null;
    return {
      total: projects.length,
      relevant: projects.filter((p) => p.esRelevante === true).length,
      sigma: projects.filter((p) => p.sigmaExpediente).length,
      coords: projects.filter((p) => p.lat != null).length,
    };
  }, [projects]);

  const clearFilters = useCallback(() => {
    setQ("");
    setTipo("");
    setRelevancia("all");
    setSigmaFilter("all");
    setYearFrom("");
    setYearTo("");
  }, []);

  if (err) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {err}
      </div>
    );
  }

  if (!projects || !stats) {
    return <div className="h-64 animate-pulse rounded-xl bg-slate-200" />;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Anuncios BOCM" value={stats.total} hint="municipio=Madrid" />
        <Stat label="Relevantes" value={stats.relevant} />
        <Stat label="Con proyecto" value={stats.sigma} hint="match por nº exp." />
        <Stat label="Con coords" value={stats.coords} />
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[200px] flex-1 space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Buscar</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Título, sector, expediente…"
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          />
        </label>
        <label className="min-w-[120px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Proyecto</span>
          <select
            value={sigmaFilter}
            onChange={(e) => setSigmaFilter(e.target.value as typeof sigmaFilter)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            <option value="all">Todos</option>
            <option value="linked">Con enlace</option>
            <option value="unlinked">Sin enlace</option>
          </select>
        </label>
        <label className="min-w-[120px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Relevancia</span>
          <select
            value={relevancia}
            onChange={(e) => setRelevancia(e.target.value as typeof relevancia)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            <option value="all">Todas</option>
            <option value="relevant">Relevante</option>
            <option value="not_relevant">No relevante</option>
            <option value="unknown">Sin clasificar</option>
          </select>
        </label>
        <label className="min-w-[140px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Instrumento</span>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm"
          >
            <option value="">Todos</option>
            {tipos.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={clearFilters}
          className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Limpiar
        </button>
      </div>

      <p className="text-sm text-slate-600">
        <span className="font-semibold text-slate-900">{filtered.length}</span> resultados
      </p>

      <ProjectsMap
        points={mapPoints}
        sectorGeoJson={sectorGeo.features?.length ? sectorGeo : null}
        dataScope="full"
        heightClassName="h-[min(40vh,420px)]"
      />

      <div className="overflow-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[880px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Fecha</th>
              <th className="px-3 py-2">Instrumento</th>
              <th className="px-3 py-2">Sector</th>
              <th className="px-3 py-2">Rel.</th>
              <th className="px-3 py-2">Proyecto</th>
              <th className="px-3 py-2">Coords</th>
              <th className="w-14" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.slice(0, 400).map((p) => (
              <tr
                key={p.id}
                onClick={() => router.push(projectPath(p.id))}
                className="cursor-pointer transition hover:bg-[var(--portal-accent-soft)]/60"
              >
                <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-700">
                  {p.bocmDate}
                </td>
                <td className="max-w-[10rem] truncate px-3 py-2 text-slate-700" title={p.tipoInstrumento}>
                  {p.tipoInstrumento || "—"}
                </td>
                <td className="max-w-xs truncate px-3 py-2 text-slate-800" title={p.nombreSector}>
                  {p.nombreSector || p.title.slice(0, 60)}
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${relevanciaBadgeClass(p.esRelevante)}`}
                  >
                    {relevanciaLabel(p.esRelevante)}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {p.sigmaExpediente ? (
                    <span className="text-sky-800" title={p.sigmaDenominacion || ""}>
                      {p.sigmaExpediente}
                    </span>
                  ) : (
                    <span className="text-slate-300">—</span>
                  )}
                </td>
                <td className="px-3 py-2 text-[10px] text-slate-500" title={coordSourceLabel(p.coordSource)}>
                  {p.lat != null ? "Sí" : "—"}
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={projectPath(p.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="text-xs font-semibold text-[var(--portal-accent)] hover:underline"
                  >
                    Ficha
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 400 ? (
          <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
            Mostrando 400 de {filtered.length}. Usa la búsqueda para acotar.
          </p>
        ) : null}
      </div>

      <p className="text-xs text-slate-500">
        Comparar con el catálogo completo en{" "}
        <Link href="/madrid/sigma" className="font-medium text-[var(--portal-accent)] hover:underline">
          proyectos de planeamiento
        </Link>
        . El enlace solo aparece si el número de expediente coincide en el catálogo descargado.
      </p>
    </div>
  );
}
