"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ensureProject } from "@/lib/ensure-project";
import type { Project } from "@/lib/types";
import { filterSectorGeoJsonForProjects } from "@/lib/filter-sector-geo";
import type { SectorFeatureCollection } from "@/lib/sector-geo";
import type { MapPoint } from "./ProjectsMap";

const ProjectsMap = dynamic(
  () => import("./ProjectsMap").then((m) => ({ default: m.ProjectsMap })),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[320px] h-[min(42vh,480px)] items-center justify-center rounded-2xl border border-dashed border-slate-200/90 bg-white/60 text-sm text-slate-500 shadow-inner lg:h-[min(52vh,560px)]">
        Cargando mapa…
      </div>
    ),
  },
);

export function LandingMap() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [sectorGeoJson, setSectorGeoJson] = useState<SectorFeatureCollection | null>(null);
  const [err, setErr] = useState<string | null>(null);

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
        if (!cancelled) setErr("No se pudo cargar el mapa.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const mapPoints: MapPoint[] = useMemo(() => {
    if (!projects?.length) return [];
    const m = new Map<string, { count: number; lat: number; lng: number }>();
    for (const p of projects) {
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
  }, [projects]);

  const sectorGeoForMap = useMemo(
    () => (projects?.length ? filterSectorGeoJsonForProjects(sectorGeoJson, projects) : null),
    [projects, sectorGeoJson],
  );

  if (err) {
    return (
      <div className="rounded-2xl border border-amber-200/90 bg-amber-50/90 px-4 py-6 text-center text-sm text-amber-950">
        <p>{err}</p>
        <p className="mt-2 text-xs text-amber-800/90">
          En la carpeta <code className="rounded bg-amber-100/80 px-1 font-mono">web/</code> ejecuta{" "}
          <code className="rounded bg-amber-100/80 px-1 font-mono">npm run build-data</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <ProjectsMap
        points={mapPoints}
        sectorGeoJson={sectorGeoForMap}
        dataScope="full"
        heightClassName="min-h-[280px] h-[min(40vh,440px)] sm:min-h-[320px] sm:h-[min(44vh,500px)] lg:min-h-[360px] lg:h-[min(52vh,580px)]"
      />
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-relaxed text-slate-500">
          Círculos: volumen por municipio. Azul: ámbito planeamiento (CM). Gris: centro aproximado (resto CCAA).
        </p>
        <Link
          href="/explore"
          className="shrink-0 text-sm font-semibold text-[var(--portal-accent)] underline-offset-4 hover:underline"
        >
          Abrir explorador con filtros →
        </Link>
      </div>
    </div>
  );
}
