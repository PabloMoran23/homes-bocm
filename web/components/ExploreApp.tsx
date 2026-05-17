"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { projectsToCsv } from "@/lib/export-csv";
import { ensureProject } from "@/lib/ensure-project";
import { projectPath } from "@/lib/project-display";
import { TIER_LABEL } from "@/lib/tiers";
import type { Project } from "@/lib/types";
import { useTier } from "@/components/TierProvider";
import { filterSectorGeoJsonForProjects } from "@/lib/filter-sector-geo";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import type { MapPoint } from "./ProjectsMap";

const ProjectsMap = dynamic(
  () => import("./ProjectsMap").then((m) => ({ default: m.ProjectsMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[min(52vh,520px)] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
        Cargando mapa…
      </div>
    ),
  },
);

function norm(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function downloadCsv(filename: string, content: string) {
  const blob = new Blob(["\uFEFF" + content], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.click();
  URL.revokeObjectURL(url);
}

export function ExploreApp() {
  const router = useRouter();
  const { tier, limits } = useTier();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [municipio, setMunicipio] = useState("");
  const [territorio, setTerritorio] = useState("");
  const [tipo, setTipo] = useState("");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [relevancia, setRelevancia] = useState<"all" | "relevant" | "not_relevant" | "unknown">(
    "all",
  );
  const [sectorGeoJson, setSectorGeoJson] = useState<SectorFeatureCollection | null>(null);

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
        if (!cancelled)
          setProjects(
            data.map((row) => ensureProject(row as Partial<Project> & { id: string })),
          );
        if (geoRes.ok && !cancelled) {
          setSectorGeoJson((await geoRes.json()) as SectorFeatureCollection);
        }
      } catch {
        if (!cancelled) setErr("No se pudo cargar el dataset. Ejecuta npm run build-data.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const bounds = useMemo(() => {
    if (!projects?.length) return { minY: "", maxY: "" };
    let min = "9999";
    let max = "0000";
    for (const p of projects) {
      const y = p.bocmDate.slice(0, 4);
      if (y.length === 4) {
        if (y < min) min = y;
        if (y > max) max = y;
      }
    }
    return { minY: min === "9999" ? "" : min, maxY: max === "0000" ? "" : max };
  }, [projects]);

  const territorios = useMemo(() => {
    if (!projects) return [];
    const s = new Set<string>();
    for (const p of projects) if (p.territorioLabel) s.add(p.territorioLabel);
    return [...s].sort((a, b) => a.localeCompare(b, "es"));
  }, [projects]);

  const municipios = useMemo(() => {
    if (!projects) return [];
    const s = new Set<string>();
    for (const p of projects) {
      if (!p.municipio) continue;
      if (territorio && p.territorioLabel !== territorio) continue;
      s.add(p.municipio);
    }
    return [...s].sort((a, b) => a.localeCompare(b, "es"));
  }, [projects, territorio]);

  const tipos = useMemo(() => {
    if (!projects) return [];
    const s = new Set<string>();
    for (const p of projects) {
      const t = p.tipoInstrumento || "Sin clasificar";
      s.add(t);
    }
    return [...s].sort((a, b) => a.localeCompare(b, "es"));
  }, [projects]);

  const filtered = useMemo(() => {
    if (!projects) return [];
    const nq = norm(q.trim());
    return projects.filter((p) => {
      if (relevancia === "relevant" && p.esRelevante !== true) return false;
      if (relevancia === "not_relevant" && p.esRelevante !== false) return false;
      if (relevancia === "unknown" && p.esRelevante != null) return false;
      if (territorio && p.territorioLabel !== territorio) return false;
      if (municipio && p.municipio !== municipio) return false;
      if (tipo && (p.tipoInstrumento || "Sin clasificar") !== tipo) return false;
      const y = p.bocmDate.slice(0, 4);
      if (yearFrom && y && y < yearFrom) return false;
      if (yearTo && y && y > yearTo) return false;
      if (!nq) return true;
      const hay =
        norm(p.title).includes(nq) ||
        norm(p.resumen).includes(nq) ||
        norm(p.municipio).includes(nq) ||
        norm(p.nombreSector).includes(nq) ||
        norm(p.territorioLabel).includes(nq) ||
        norm(p.organo).includes(nq) ||
        norm(p.promotor || "").includes(nq) ||
        norm(p.categoriasTematicas || "").includes(nq) ||
        norm(p.economicoResumen || "").includes(nq) ||
        norm(p.procedimientoExpediente || "").includes(nq);
      return hay;
    });
  }, [projects, q, municipio, territorio, tipo, yearFrom, yearTo, relevancia]);

  const mapPoints: MapPoint[] = useMemo(() => {
    const m = new Map<string, { count: number; lat: number; lng: number }>();
    for (const p of filtered) {
      if (p.lat == null || p.lng == null || !p.municipio) continue;
      const cur = m.get(p.municipio);
      if (cur) cur.count += 1;
      else m.set(p.municipio, { count: 1, lat: p.lat, lng: p.lng });
    }
    return [...m.entries()].map(([municipio, v]) => ({
      municipio,
      count: v.count,
      lat: v.lat,
      lng: v.lng,
    }));
  }, [filtered]);

  const filteredSectorGeo = useMemo(
    () => filterSectorGeoJsonForProjects(sectorGeoJson, filtered),
    [filtered, sectorGeoJson],
  );

  const clearFilters = useCallback(() => {
    setQ("");
    setMunicipio("");
    setTerritorio("");
    setTipo("");
    setYearFrom("");
    setYearTo("");
    setRelevancia("all");
  }, []);

  const cap = limits.maxTableRows;
  const rows = filtered.slice(0, cap);
  const truncatedTable = filtered.length > cap;

  const onExportCsv = useCallback(() => {
    if (!limits.exportFilteredCsv || !filtered.length) return;
    const csv = projectsToCsv(filtered);
    const stamp = new Date().toISOString().slice(0, 10);
    downloadCsv(`urbanismo-filtrado-${stamp}.csv`, csv);
  }, [limits.exportFilteredCsv, filtered]);

  if (err) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {err}
      </div>
    );
  }

  if (!projects) {
    return (
      <div className="space-y-3">
        <div className="h-10 max-w-md animate-pulse rounded-lg bg-slate-200" />
        <div className="h-[min(52vh,520px)] animate-pulse rounded-xl bg-slate-200" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <p>
          Plan activo:{" "}
          <span className="font-semibold text-slate-900">{TIER_LABEL[tier]}</span>
          {tier === "free" ? (
            <>
              {" "}
              ·{" "}
              <Link
                href="/planes"
                className="font-medium text-[var(--portal-accent)] underline-offset-2 hover:underline"
              >
                Ver otros planes
              </Link>
            </>
          ) : null}
        </p>
        {limits.exportFilteredCsv ? (
          <button
            type="button"
            onClick={onExportCsv}
            disabled={filtered.length === 0}
            className="shrink-0 rounded-md border border-[var(--portal-accent)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--portal-accent)] shadow-sm transition hover:bg-[var(--portal-accent-soft)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Exportar CSV ({filtered.length})
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="min-w-[200px] flex-1 space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Buscar
          </span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Título, resumen, municipio, economía, categorías…"
            className="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none ring-[var(--portal-accent)]/25 focus:border-[var(--portal-accent)] focus:ring-2"
          />
        </label>
        <label className="min-w-[150px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Relevancia
          </span>
          <select
            value={relevancia}
            onChange={(e) =>
              setRelevancia(e.target.value as "all" | "relevant" | "not_relevant" | "unknown")
            }
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          >
            <option value="all">Todos (CSV completo)</option>
            <option value="relevant">Solo relevantes</option>
            <option value="not_relevant">No relevantes</option>
            <option value="unknown">Sin clasificar</option>
          </select>
        </label>
        <label className="min-w-[160px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Territorio
          </span>
          <select
            value={territorio}
            onChange={(e) => {
              setTerritorio(e.target.value);
              setMunicipio("");
            }}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          >
            <option value="">Todos ({territorios.length})</option>
            {territorios.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-[140px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Municipio
          </span>
          <select
            value={municipio}
            onChange={(e) => setMunicipio(e.target.value)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          >
            <option value="">Todos ({municipios.length})</option>
            {municipios.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-[160px] space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Instrumento
          </span>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
            className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          >
            <option value="">Todos</option>
            {tipos.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="w-24 space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Año desde
          </span>
          <input
            type="number"
            value={yearFrom}
            onChange={(e) => setYearFrom(e.target.value)}
            placeholder={bounds.minY}
            className="w-full rounded-md border border-slate-200 px-2 py-2 text-sm tabular-nums outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          />
        </label>
        <label className="w-24 space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Año hasta
          </span>
          <input
            type="number"
            value={yearTo}
            onChange={(e) => setYearTo(e.target.value)}
            placeholder={bounds.maxY}
            className="w-full rounded-md border border-slate-200 px-2 py-2 text-sm tabular-nums outline-none focus:border-[var(--portal-accent)] focus:ring-2 focus:ring-[var(--portal-accent)]/25"
          />
        </label>
        <button
          type="button"
          onClick={clearFilters}
          className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Limpiar
        </button>
      </div>

      <p className="text-sm text-slate-600">
        <span className="font-semibold text-slate-900">{filtered.length}</span>{" "}
        resultados
        {projects ? (
          <span className="text-slate-500">
            {" "}
            · {projects.length.toLocaleString("es-ES")} en dataset (todo el CSV)
          </span>
        ) : null}
        {truncatedTable ? (
          <span className="text-slate-500">
            {" "}
            (tabla limitada a {cap} por plan {TIER_LABEL[tier]})
          </span>
        ) : null}
      </p>

      {truncatedTable ? (
        <div className="rounded-lg border border-[var(--portal-accent-soft)] bg-[var(--portal-accent-soft)]/50 px-4 py-3 text-sm text-slate-900">
          Hay más resultados que los que tu plan muestra en la tabla. El mapa sigue reflejando{" "}
          <strong className="font-semibold">todos</strong> los puntos del filtro actual.{" "}
          <Link href="/planes" className="font-semibold text-[var(--portal-accent)] underline underline-offset-2">
            Subir de plan
          </Link>{" "}
          o exportar CSV en <strong className="font-semibold">Empresa</strong>.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <ProjectsMap points={mapPoints} sectorGeoJson={filteredSectorGeo} />
        </div>
        <div className="min-h-[320px] overflow-auto rounded-xl border border-slate-200 bg-white lg:col-span-3">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Fecha</th>
                <th className="px-3 py-2">Territorio</th>
                <th className="px-3 py-2">Municipio</th>
                <th className="px-3 py-2">Instrumento</th>
                <th className="px-3 py-2">Rel.</th>
                <th className="px-3 py-2">Trámite</th>
                <th className="px-3 py-2 w-16" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => router.push(projectPath(p.id))}
                  className={`cursor-pointer transition hover:bg-[var(--portal-accent-soft)]/70 ${
                    p.esRelevante === false ? "opacity-80" : ""
                  }`}
                >
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums text-slate-700">
                    {p.bocmDate}
                  </td>
                  <td className="px-3 py-2 text-slate-600" title={p.territorioLabel}>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">
                      {p.territorioLabel}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-medium text-slate-900">{p.municipio}</td>
                  <td className="max-w-[200px] truncate px-3 py-2 text-slate-600" title={p.tipoInstrumento}>
                    {p.tipoInstrumento}
                  </td>
                  <td className="px-3 py-2">
                    {p.esRelevante === true ? (
                      <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-800">
                        Sí
                      </span>
                    ) : p.esRelevante === false ? (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">
                        No
                      </span>
                    ) : (
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-900">
                        ?
                      </span>
                    )}
                  </td>
                  <td className="max-w-[180px] truncate px-3 py-2 text-slate-600" title={p.estadoTramitacion}>
                    {p.estadoTramitacion}
                  </td>
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <Link
                      href={projectPath(p.id)}
                      className="text-xs font-semibold text-[var(--portal-accent)] hover:underline"
                    >
                      Ficha
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-center text-xs text-slate-500">
        Haz clic en una fila para abrir la{" "}
        <span className="font-medium text-slate-700">ficha completa del proyecto</span> (mapa, SIGMA,
        PDF y todos los campos del CSV).
      </p>
    </div>
  );
}
