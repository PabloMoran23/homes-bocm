"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { KpiCard } from "@/components/madrid/dashboard/KpiCard";
import type { MunicipioBotRow, MunicipioBotsPayload } from "@/lib/types";

const POLL_MS = 20_000;

type StatusFilter = "all" | "done" | "pending" | "in_progress" | "failed" | "skipped";

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

function statusBadge(status: string) {
  const styles: Record<string, string> = {
    done: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    pending: "bg-slate-100 text-slate-700 ring-slate-200",
    in_progress: "bg-sky-50 text-sky-800 ring-sky-200",
    failed: "bg-red-50 text-red-800 ring-red-200",
    skipped: "bg-amber-50 text-amber-900 ring-amber-200",
  };
  const cls = styles[status] ?? "bg-slate-100 text-slate-700 ring-slate-200";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${cls}`}>
      {status}
    </span>
  );
}

function boolIcon(ok: boolean) {
  return ok ? (
    <span className="font-semibold text-emerald-600" title="Sí">
      ✓
    </span>
  ) : (
    <span className="text-slate-300" title="No">
      —
    </span>
  );
}

function parityBadge(level: string | null | undefined) {
  if (!level) return <span className="text-slate-400">—</span>;
  const styles: Record<string, string> = {
    ok: "text-emerald-700",
    partial: "text-amber-700",
    none: "text-red-600",
  };
  return <span className={`text-xs font-semibold ${styles[level] ?? "text-slate-600"}`}>{level}</span>;
}

export function MunicipioBotsPanel() {
  const [data, setData] = useState<MunicipioBotsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchErr, setFetchErr] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [ccaaFilter, setCcaaFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

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

  const ccaaOptions = useMemo(() => {
    const rows = data?.municipios ?? [];
    const map = new Map<string, string>();
    for (const r of rows) map.set(r.comunidadAutonoma, r.comunidadLabel);
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1], "es"));
  }, [data]);

  const filtered = useMemo(() => {
    const rows = data?.municipios ?? [];
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (statusFilter !== "all" && r.status !== statusFilter) return false;
      if (ccaaFilter !== "all" && r.comunidadAutonoma !== ccaaFilter) return false;
      if (!q) return true;
      return (
        r.slug.includes(q) ||
        r.nombre.toLowerCase().includes(q) ||
        r.provincia.toLowerCase().includes(q)
      );
    });
  }, [data, statusFilter, ccaaFilter, query]);

  const mergedRecent = useMemo(() => {
    return (data?.municipios ?? [])
      .filter((r) => r.status === "done" && r.hasManifest)
      .sort((a, b) => (b.activityAt ?? "").localeCompare(a.activityAt ?? ""))
      .slice(0, 8);
  }, [data]);

  if (loading && !data) {
    return <p className="text-sm text-slate-500">Cargando panel de municipios…</p>;
  }

  const summary = data?.summary;
  const next = data?.next as MunicipioBotRow | null | undefined;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-600">
            Seguimiento de la cola de onboarding y adapters mergeados en{" "}
            <code className="rounded bg-slate-100 px-1 text-xs">main</code>.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Actualizado: {fmtDate(data?.generatedAt)} · Cola YAML: {fmtDate(data?.queueUpdatedAt)}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Refrescar
        </button>
      </div>

      {fetchErr ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Aviso API: {fetchErr}
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="En cola" value={String(summary?.total ?? 0)} hint="Municipios en queue.yaml" />
        <KpiCard
          label="Mergeados"
          value={String(summary?.byStatus?.done ?? 0)}
          hint="status=done"
          accent="teal"
        />
        <KpiCard
          label="Pendientes"
          value={String(summary?.byStatus?.pending ?? 0)}
          hint="Esperando bot"
          accent="sky"
        />
        <KpiCard
          label="Con adapter"
          value={String(summary?.withAdapter ?? 0)}
          hint="manifest + .py en repo"
        />
        <KpiCard
          label="Con polígonos"
          value={String(summary?.withPortalGeometry ?? 0)}
          hint="parity with_geometry &gt; 0"
          accent="amber"
        />
        <KpiCard
          label="PRs abiertas"
          value={String(summary?.openPrs ?? 0)}
          hint="Automation en curso"
          accent="amber"
        />
      </div>

      {next ? (
        <section className="rounded-xl border border-sky-200 bg-sky-50/70 p-4 ring-1 ring-sky-100">
          <h2 className="text-sm font-semibold text-sky-950">Siguiente en cola</h2>
          <p className="mt-1 text-sm text-sky-900">
            <strong>{next.nombre}</strong> ({next.slug}) · {next.comunidadLabel} ·{" "}
            {next.bocmCount} en boletín · fuente {next.boletinSourceId}
          </p>
        </section>
      ) : null}

      {mergedRecent.length > 0 ? (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-900">Últimos mergeados</h2>
          <ul className="mt-3 divide-y divide-slate-100">
            {mergedRecent.map((r) => (
              <li key={r.slug} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <div>
                  <span className="font-medium text-slate-900">{r.nombre}</span>
                  <span className="ml-2 text-xs text-slate-500">{r.comunidadLabel}</span>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
                  <span>{fmtDate(r.activityAt)}</span>
                  <span>
                    {r.proyectosRows} proy · {r.withGeometry} geom
                  </span>
                  {r.prUrl ? (
                    <a
                      href={r.prUrl}
                      className="text-[var(--portal-accent)] hover:underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      PR
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm ring-1 ring-slate-900/[0.03]">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 p-4">
          <input
            type="search"
            placeholder="Buscar municipio…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-w-[200px] flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          >
            <option value="all">Todos los estados</option>
            <option value="done">done</option>
            <option value="pending">pending</option>
            <option value="in_progress">in_progress</option>
            <option value="failed">failed</option>
            <option value="skipped">skipped</option>
          </select>
          <select
            value={ccaaFilter}
            onChange={(e) => setCcaaFilter(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          >
            <option value="all">Todas las CCAA</option>
            {ccaaOptions.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
          <span className="text-xs text-slate-500">{filtered.length} filas</span>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Municipio</th>
                <th className="px-4 py-3">CCAA</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Boletín</th>
                <th className="px-4 py-3">M+A</th>
                <th className="px-4 py-3">Datos portal</th>
                <th className="px-4 py-3">Parity</th>
                <th className="px-4 py-3">Actividad</th>
                <th className="px-4 py-3">PR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.slice(0, 500).map((r) => (
                <Fragment key={r.slug}>
                  <tr className="hover:bg-slate-50/80" onClick={() => setExpanded(expanded === r.slug ? null : r.slug)}>
                    <td className="cursor-pointer px-4 py-3">
                      <div className="font-medium text-slate-900">{r.nombre}</div>
                      <div className="text-xs text-slate-500">{r.slug}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">
                      <div>{r.comunidadLabel}</div>
                      {r.provincia ? <div className="text-slate-400">{r.provincia}</div> : null}
                    </td>
                    <td className="px-4 py-3">
                      {statusBadge(r.status)}
                      {r.blockedReason ? (
                        <div className="mt-1 text-[10px] text-amber-700">{r.blockedReason}</div>
                      ) : null}
                      {r.attempts > 0 ? (
                        <div className="mt-1 text-[10px] text-slate-400">{r.attempts} intentos</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 tabular-nums">
                      <div className="font-medium">{r.bocmCount}</div>
                      <div className="text-[10px] uppercase text-slate-400">{r.boletinSourceId}</div>
                    </td>
                    <td className="px-4 py-3">{boolIcon(r.hasManifest && r.hasAdapter)}</td>
                    <td className="px-4 py-3 tabular-nums">
                      <div>{r.proyectosRows} proy</div>
                      <div className="text-xs text-slate-500">
                        {r.withCoords} coords · {r.withGeometry} geom
                      </div>
                      <div className="text-xs text-slate-400">{r.licenciasRows} lic</div>
                    </td>
                    <td className="px-4 py-3">{parityBadge(r.parityOverall)}</td>
                    <td className="px-4 py-3 text-xs text-slate-600">
                      <div>{fmtDate(r.activityAt)}</div>
                      {r.mergeCommit ? (
                        <div className="font-mono text-[10px] text-slate-400">{r.mergeCommit}</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {r.openPrUrl ? (
                        <a
                          href={r.openPrUrl}
                          className="font-medium text-sky-700 hover:underline"
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          abierta
                        </a>
                      ) : r.prUrl ? (
                        <a
                          href={r.prUrl}
                          className="text-[var(--portal-accent)] hover:underline"
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          mergeada
                        </a>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                  {expanded === r.slug ? (
                    <tr className="bg-slate-50/50">
                      <td colSpan={9} className="px-4 py-3 text-xs text-slate-600">
                        <div className="grid gap-2 md:grid-cols-2">
                          {r.portalUrl ? (
                            <p>
                              <span className="font-semibold text-slate-700">Portal:</span>{" "}
                              <a
                                href={r.portalUrl}
                                className="text-[var(--portal-accent)] hover:underline"
                                target="_blank"
                                rel="noreferrer"
                              >
                                {r.portalUrl}
                              </a>
                            </p>
                          ) : null}
                          {r.adapterPath ? (
                            <p>
                              <span className="font-semibold text-slate-700">Adapter:</span>{" "}
                              <code>{r.adapterPath}</code>
                            </p>
                          ) : null}
                          {r.mergeSubject ? (
                            <p>
                              <span className="font-semibold text-slate-700">Commit:</span> {r.mergeSubject}
                            </p>
                          ) : null}
                          {r.notes ? (
                            <p>
                              <span className="font-semibold text-slate-700">Notas:</span> {r.notes}
                            </p>
                          ) : null}
                          {r.lastError ? (
                            <p className="text-red-700">
                              <span className="font-semibold">Error:</span> {r.lastError}
                            </p>
                          ) : null}
                          {!r.hasResearch ? <p className="text-amber-700">Falta RESEARCH.md</p> : null}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length > 500 ? (
          <p className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
            Mostrando 500 de {filtered.length}. Usa filtros para acotar.
          </p>
        ) : null}
      </section>
    </div>
  );
}
