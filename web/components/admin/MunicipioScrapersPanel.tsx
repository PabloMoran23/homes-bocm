"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { MiniRoscoKpi } from "@/components/admin/MiniRoscoKpi";
import { KpiCard } from "@/components/madrid/dashboard/KpiCard";
import type {
  MunicipioBotRow,
  MunicipioBotsPayload,
  MunicipioCompletenessBand,
  MunicipioFillRates,
  MunicipioFreshness,
} from "@/lib/types";

const ROSCO_TEAL = "#1f4f53";
const ROSCO_COLORS = ["#1f4f53", "#4a7578", "#6b8f54", "#d4923a", "#c07f6c", "#7a5c58", "#5f7a4a", "#4a7578"];

const POLL_MS = 60_000;

const FILL_LABELS: { key: keyof MunicipioFillRates; label: string }[] = [
  { key: "titulo", label: "Título" },
  { key: "fecha", label: "Fecha" },
  { key: "url", label: "URL" },
  { key: "coords", label: "Coords" },
  { key: "geometry", label: "Polígono" },
  { key: "pdf", label: "PDF" },
  { key: "expediente", label: "Expte" },
  { key: "tipo", label: "Tipo" },
  { key: "resumen", label: "Resumen" },
  { key: "metrics", label: "Métricas" },
  { key: "visor", label: "Visor" },
];

const BAND_LABEL: Record<MunicipioCompletenessBand, string> = {
  rico: "Rico",
  medio: "Medio",
  basico: "Básico",
  fino: "Fino",
  sin_datos: "Sin datos",
};

const BAND_CLASS: Record<MunicipioCompletenessBand, string> = {
  rico: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  medio: "bg-sky-50 text-sky-800 ring-sky-200",
  basico: "bg-amber-50 text-amber-900 ring-amber-200",
  fino: "bg-slate-100 text-slate-700 ring-slate-200",
  sin_datos: "bg-slate-50 text-slate-500 ring-slate-200",
};

const FRESH_LABEL: Record<MunicipioFreshness, string> = {
  fresh: "Al día",
  due: "Vencido",
  never: "Nunca",
  error: "Error",
  unknown: "—",
};

const FRESH_CLASS: Record<MunicipioFreshness, string> = {
  fresh: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  due: "bg-amber-50 text-amber-900 ring-amber-200",
  never: "bg-slate-100 text-slate-600 ring-slate-200",
  error: "bg-red-50 text-red-800 ring-red-200",
  unknown: "bg-slate-50 text-slate-500 ring-slate-200",
};

type SortLive = "age" | "proyectos" | "nombre";
type SortComplete = "score" | "proyectos" | "nombre";

function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("es-ES", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function fmtNum(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("es-ES");
}

function pct(rate: number | null | undefined) {
  if (rate == null || Number.isNaN(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
}

function ageLabel(days: number | null | undefined) {
  if (days == null) return "—";
  if (days < 1) return `${Math.round(days * 24)} h`;
  if (days < 10) return `${days.toFixed(1)} d`;
  return `${Math.round(days)} d`;
}

function pill(text: string, className: string) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${className}`}>
      {text}
    </span>
  );
}

function ScoreBar({ score }: { score: number }) {
  const width = Math.max(0, Math.min(100, score));
  const tone =
    score >= 65 ? "bg-emerald-500" : score >= 40 ? "bg-sky-500" : score >= 20 ? "bg-amber-500" : "bg-slate-400";
  return (
    <div className="flex min-w-[7rem] items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${width}%` }} />
      </div>
      <span className="w-8 text-right text-xs font-semibold tabular-nums text-slate-700">{score}</span>
    </div>
  );
}

function matchesQuery(row: MunicipioBotRow, q: string) {
  if (!q) return true;
  return (
    row.slug.includes(q) ||
    row.nombre.toLowerCase().includes(q) ||
    row.provincia.toLowerCase().includes(q) ||
    row.comunidadLabel.toLowerCase().includes(q)
  );
}

export function MunicipioScrapersPanel() {
  const [data, setData] = useState<MunicipioBotsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchErr, setFetchErr] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [onlyAdapters, setOnlyAdapters] = useState(true);
  const [sortLive, setSortLive] = useState<SortLive>("age");
  const [sortComplete, setSortComplete] = useState<SortComplete>("score");

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/admin/municipio-bots", { cache: "no-store" });
      const j = (await r.json()) as MunicipioBotsPayload & { error?: string };
      setData(j);
      setFetchErr(j.error ?? null);
    } catch (e) {
      setFetchErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const run = () => void load();
    const t0 = window.setTimeout(run, 0);
    const id = window.setInterval(run, POLL_MS);
    return () => {
      window.clearTimeout(t0);
      window.clearInterval(id);
    };
  }, [load]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.municipios ?? []).filter((r) => {
      if (onlyAdapters && !r.hasAdapter) return false;
      return matchesQuery(r, q);
    });
  }, [data, onlyAdapters, query]);

  const liveRows = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      if (sortLive === "proyectos") return (b.proyectosRows || 0) - (a.proyectosRows || 0);
      if (sortLive === "nombre") return a.nombre.localeCompare(b.nombre, "es");
      const ae = a.freshness === "error" ? 0 : a.freshness === "never" ? 1 : a.freshness === "due" ? 2 : 3;
      const be = b.freshness === "error" ? 0 : b.freshness === "never" ? 1 : b.freshness === "due" ? 2 : 3;
      if (ae !== be) return ae - be;
      return (b.ingestAgeDays ?? -1) - (a.ingestAgeDays ?? -1);
    });
    return copy;
  }, [rows, sortLive]);

  const completeRows = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      if (sortComplete === "proyectos") return (b.proyectosRows || 0) - (a.proyectosRows || 0);
      if (sortComplete === "nombre") return a.nombre.localeCompare(b.nombre, "es");
      return (b.completenessScore ?? 0) - (a.completenessScore ?? 0);
    });
    return copy;
  }, [rows, sortComplete]);

  const coverage = useMemo(() => {
    const all = data?.municipios ?? [];
    const total = all.length || data?.summary.total || 0;
    const adapters = all.filter((r) => r.hasAdapter);
    const n = adapters.length;
    const has = (pred: (r: MunicipioBotRow) => boolean) => adapters.filter(pred).length;
    const blocks = [
      {
        label: "Proyectos",
        value: has((r) => (r.proyectosRows || 0) > 0),
        hint: "Al menos un proyecto",
      },
      {
        label: "Coordenadas",
        value: has((r) => (r.withCoords || 0) > 0),
        hint: "Punto en el mapa",
      },
      {
        label: "Polígono",
        value: has((r) => (r.withGeometry || 0) > 0),
        hint: "Ámbito con geometría",
      },
      {
        label: "Documentos",
        value: has((r) => (r.withPdf || 0) > 0),
        hint: "PDF o listado NTI",
      },
      {
        label: "Expediente",
        value: has((r) => (r.withExpediente || 0) > 0),
        hint: "Código de expediente",
      },
      {
        label: "Resumen",
        value: has((r) => (r.fill?.resumen || 0) > 0),
        hint: "Texto más allá del título",
      },
      {
        label: "Visor",
        value: has((r) => (r.fill?.visor || 0) > 0),
        hint: "Ficha / tramitación ayto.",
      },
      {
        label: "Licencias",
        value: has((r) => (r.licenciasRows || 0) > 0),
        hint: "Filas de licencias o trámites",
      },
    ];
    return { total, withScraper: n, blocks };
  }, [data]);

  if (loading && !data) {
    return <p className="text-sm text-slate-500">Cargando estado de scrapers…</p>;
  }

  const live = data?.summary.live;
  const completeness = data?.summary.completeness;
  const bandTotal =
    (completeness?.byBand.rico ?? 0) +
    (completeness?.byBand.medio ?? 0) +
    (completeness?.byBand.basico ?? 0) +
    (completeness?.byBand.fino ?? 0) +
    (completeness?.byBand.sin_datos ?? 0);

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-600">
            Cadencia de ingest y riqueza de ficha por municipio. No aparece en la web pública.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Actualizado: {fmtDate(data?.generatedAt)}
            {data?.dbAvailable ? " · datos de Supabase + JSONL local" : " · sin Supabase (solo JSONL / cola)"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={onlyAdapters}
              onChange={(e) => setOnlyAdapters(e.target.checked)}
            />
            Solo con adapter
          </label>
          <input
            type="search"
            placeholder="Buscar municipio…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-w-[200px] rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Refrescar
          </button>
        </div>
      </div>

      {fetchErr ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Aviso API: {fetchErr}
        </div>
      ) : null}

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Cómo vamos</h2>
          <p className="mt-1 text-sm text-slate-600">
            Cobertura de scrapers sobre la cola, y cuántos de esos municipios traen cada bloque de información.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <MiniRoscoKpi
              label="Con scraper"
              value={coverage.withScraper}
              total={coverage.total}
              hint="Municipios con adapter del total en cola"
              color={ROSCO_TEAL}
              featured
            />
          </div>
          {coverage.blocks.map((block, i) => (
            <MiniRoscoKpi
              key={block.label}
              label={block.label}
              value={block.value}
              total={coverage.withScraper}
              hint={`${block.hint} · de ${coverage.withScraper.toLocaleString("es-ES")} con scraper`}
              color={ROSCO_COLORS[i % ROSCO_COLORS.length]}
            />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">En vivo</h2>
          <p className="mt-1 text-sm text-slate-600">
            Última ingest (cadencia ~15 días), volumen de proyectos y licencias.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <KpiCard label="Al día" value={fmtNum(live?.fresh)} hint="Ingest de menos de 18 días" accent="teal" />
          <KpiCard label="Vencidos" value={fmtNum(live?.due)} hint="Toca refrescar" accent="amber" />
          <KpiCard label="Nunca ingestados" value={fmtNum(live?.never)} hint="Adapter sin last_ingest" />
          <KpiCard label="Con error" value={fmtNum(live?.error)} hint="status=failed" accent="amber" />
          <KpiCard
            label="Proyectos"
            value={fmtNum(live?.totalProyectos)}
            hint="Suma de filas portal"
            accent="sky"
          />
          <KpiCard label="Licencias" value={fmtNum(live?.totalLicencias)} hint="Suma de filas portal" />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-medium text-slate-500">Ordenar</label>
          <select
            value={sortLive}
            onChange={(e) => setSortLive(e.target.value as SortLive)}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
          >
            <option value="age">Más urgentes</option>
            <option value="proyectos">Más proyectos</option>
            <option value="nombre">Nombre</option>
          </select>
          <span className="text-xs text-slate-500">{liveRows.length} municipios</span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Municipio</th>
                <th className="px-4 py-3">Estado scrape</th>
                <th className="px-4 py-3">Última ingest</th>
                <th className="px-4 py-3">Edad</th>
                <th className="px-4 py-3">Proyectos</th>
                <th className="px-4 py-3">Licencias</th>
                <th className="px-4 py-3">Coords / geom</th>
                <th className="px-4 py-3">Fuente</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {liveRows.slice(0, 400).map((r) => (
                <tr key={`live-${r.slug}`} className="hover:bg-slate-50/80">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{r.nombre}</div>
                    <div className="text-xs text-slate-500">
                      {r.slug} · {r.comunidadLabel}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {pill(FRESH_LABEL[r.freshness ?? "unknown"], FRESH_CLASS[r.freshness ?? "unknown"])}
                    {r.lastError ? (
                      <div className="mt-1 max-w-[16rem] truncate text-[10px] text-red-700" title={r.lastError}>
                        {r.lastError}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    <div>{fmtDate(r.lastIngestAt || r.lastOutputAt)}</div>
                    {r.lastOutputAt && r.lastIngestAt && r.lastOutputAt !== r.lastIngestAt ? (
                      <div className="text-slate-400">JSONL {fmtDate(r.lastOutputAt)}</div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-slate-700">{ageLabel(r.ingestAgeDays)}</td>
                  <td className="px-4 py-3 tabular-nums font-medium">{fmtNum(r.proyectosRows)}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">{fmtNum(r.licenciasRows)}</td>
                  <td className="px-4 py-3 text-xs tabular-nums text-slate-600">
                    {fmtNum(r.withCoords)} / {fmtNum(r.withGeometry)}
                  </td>
                  <td className="px-4 py-3 text-[11px] uppercase text-slate-400">{r.dataSource ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Completitud</h2>
          <p className="mt-1 text-sm text-slate-600">
            Qué trae cada ficha: polígono, PDF, expediente, resumen propio, visor. El score 0–100 pondera esos
            campos (Madrid capital suele quedar en rico).
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard
            label="Score medio"
            value={completeness ? String(completeness.avgScore) : "—"}
            hint={`${fmtNum(completeness?.scoredAdapters)} adapters con proyectos`}
            accent="teal"
          />
          <KpiCard label="Ricos" value={fmtNum(completeness?.byBand.rico)} hint="Score ≥ 65" accent="teal" />
          <KpiCard label="Medios" value={fmtNum(completeness?.byBand.medio)} hint="40–64" accent="sky" />
        </div>

        {completeness && bandTotal > 0 ? (
          <div className="flex h-3 overflow-hidden rounded-full ring-1 ring-slate-200">
            {(
              [
                ["rico", "bg-emerald-500"],
                ["medio", "bg-sky-500"],
                ["basico", "bg-amber-400"],
                ["fino", "bg-slate-400"],
                ["sin_datos", "bg-slate-200"],
              ] as const
            ).map(([band, color]) => {
              const n = completeness.byBand[band] || 0;
              if (!n) return null;
              return (
                <div
                  key={band}
                  className={color}
                  style={{ width: `${(100 * n) / bandTotal}%` }}
                  title={`${BAND_LABEL[band]}: ${n}`}
                />
              );
            })}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-medium text-slate-500">Ordenar</label>
          <select
            value={sortComplete}
            onChange={(e) => setSortComplete(e.target.value as SortComplete)}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
          >
            <option value="score">Más completos</option>
            <option value="proyectos">Más proyectos</option>
            <option value="nombre">Nombre</option>
          </select>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Municipio</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Banda</th>
                <th className="px-4 py-3">Proy.</th>
                {FILL_LABELS.map((f) => (
                  <th key={f.key} className="px-2 py-3 text-center">
                    {f.label}
                  </th>
                ))}
                <th className="px-4 py-3">GIS research</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {completeRows.slice(0, 400).map((r) => (
                <tr key={`c-${r.slug}`} className="hover:bg-slate-50/80">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{r.nombre}</div>
                    <div className="text-xs text-slate-500">{r.slug}</div>
                  </td>
                  <td className="px-4 py-3">
                    <ScoreBar score={r.completenessScore ?? 0} />
                  </td>
                  <td className="px-4 py-3">
                    {pill(
                      BAND_LABEL[r.completenessBand ?? "sin_datos"],
                      BAND_CLASS[r.completenessBand ?? "sin_datos"],
                    )}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{fmtNum(r.proyectosRows)}</td>
                  {FILL_LABELS.map((f) => (
                    <td key={f.key} className="px-2 py-3 text-center text-[11px] tabular-nums text-slate-600">
                      {pct(r.fill?.[f.key])}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-xs text-slate-500">{r.geometryStatus ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
