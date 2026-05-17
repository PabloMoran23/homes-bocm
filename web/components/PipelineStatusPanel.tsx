"use client";

import { useCallback, useEffect, useState } from "react";
import type { PipelineStatusPayload } from "@/lib/types";

const POLL_MS = 12_000;

function num(n: unknown) {
  if (typeof n !== "number" || Number.isNaN(n)) return "—";
  return n.toLocaleString("es-ES");
}

function pct(done: unknown, total: unknown) {
  if (typeof done !== "number" || typeof total !== "number" || total <= 0) return "—";
  return `${Math.min(100, Math.round((100 * done) / total))}%`;
}

function phaseLabel(phase: string) {
  const m: Record<string, string> = {
        visor_fetch: "Visor + NTI (fetch)",
        ingest_sqlite: "Volcado SQLite (ingest)",
    descarga_nti: "Descarga PDFs NTI",
    completado: "Completado (última pasada)",
    desconocido: "Sin fase detectada",
    error: "Error al leer estado",
  };
  return m[phase] ?? phase;
}

export function PipelineStatusPanel() {
  const [data, setData] = useState<PipelineStatusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchErr, setFetchErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/admin/pipeline-status", { cache: "no-store" });
      const j = (await r.json()) as PipelineStatusPayload;
      setData(j);
      setFetchErr(null);
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

  if (loading && !data) {
    return (
      <section className="mb-10 rounded-xl border border-slate-200 bg-white p-6 shadow-sm ring-1 ring-slate-100">
        <h2 className="text-lg font-semibold text-slate-900">Pipeline SIGMA / NTI</h2>
        <p className="mt-2 text-sm text-slate-500">Cargando estado…</p>
      </section>
    );
  }

  const sqlite = data?.sqlite ?? {};
  const visorJson = data?.visorJson ?? {};
  const log = data?.log;
  const proc = data?.processes;

  const fetchCur = log?.fetchCurrent ?? null;
  const fetchTot = log?.fetchTotal ?? null;

  const ntiTotal = sqlite.ntiDocumentRows as number | undefined;
  const ntiOk = sqlite.ntiDescargados as number | undefined;

  const visorStale =
    proc?.visorFetchRunning &&
    typeof sqlite.sigmaCatalogExpedientes === "number" &&
    typeof visorJson.expedientesEnJson === "number" &&
    (visorJson.expedientesEnJson as number) > 50 &&
    (visorJson.expedientesEnJson as number) + 400 < (sqlite.sigmaCatalogExpedientes as number);

  return (
    <section className="mb-10 rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 via-white to-white p-6 shadow-sm ring-1 ring-indigo-100">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Pipeline SIGMA / NTI</h2>
          <p className="mt-1 text-sm text-slate-600">
            Estado local (SQLite, log batch, proceso). Actualización cada {POLL_MS / 1000}s.
          </p>
        </div>
        <button
          type="button"
          onClick={() => load()}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Refrescar
        </button>
      </div>

      {data?.error ? (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
          <strong>Python / SQLite:</strong> {data.error}
        </p>
      ) : null}
      {fetchErr ? (
        <p className="mt-2 text-xs text-red-700">Red: {fetchErr}</p>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-white/70 bg-white/90 px-3 py-3 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Fase actual</p>
          <p className="mt-1 text-base font-semibold text-slate-900">
            {phaseLabel(log?.phase ?? "desconocido")}
          </p>
          <p className="mt-2 text-[11px] text-slate-500">
            {proc?.pipelineScriptRunning ? "Script bash activo · " : ""}
            {proc?.visorFetchRunning ? "Fetcher Python activo" : "Fetcher detenido"}
            {proc?.downloadRunning ? " · Descarga NTI activa" : ""}
          </p>
        </div>
        <div className="rounded-lg border border-white/70 bg-white/90 px-3 py-3 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Visor fetch (log)</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
            {fetchCur != null && fetchTot != null ? (
              <>
                {num(fetchCur)}{" "}
                <span className="text-base font-normal text-slate-500">/ {num(fetchTot)}</span>
              </>
            ) : (
              "—"
            )}
          </p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-2 rounded-full bg-indigo-600 transition-all duration-500"
              style={{
                width:
                  fetchCur != null && fetchTot != null && fetchTot > 0
                    ? `${Math.min(100, (100 * fetchCur) / fetchTot)}%`
                    : "4%",
              }}
            />
          </div>
          <p className="mt-1 text-[11px] text-slate-500">{pct(fetchCur ?? 0, fetchTot ?? 0)} · estimación desde log</p>
        </div>
        <div className="rounded-lg border border-white/70 bg-white/90 px-3 py-3 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">NTI descargados (DB)</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
            {ntiOk ?? "—"}
            <span className="text-base font-normal text-slate-500"> / {num(ntiTotal)}</span>
          </p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-2 rounded-full bg-emerald-600 transition-all duration-500"
              style={{
                width:
                  typeof ntiTotal === "number" && ntiTotal > 0 && typeof ntiOk === "number"
                    ? `${Math.min(100, (100 * ntiOk) / ntiTotal)}%`
                    : "4%",
              }}
            />
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            Pendientes: {num(sqlite.ntiPendientes)} · Errores:{" "}
            <span className={Number(sqlite.ntiConError) > 0 ? "font-semibold text-red-700" : ""}>
              {num(sqlite.ntiConError)}
            </span>
          </p>
        </div>
        <div className="rounded-lg border border-white/70 bg-white/90 px-3 py-3 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Catálogo / trámites</p>
          <p className="mt-2 text-xs text-slate-600 leading-relaxed">
            Expedientes SQLite:{" "}
            <span className="font-mono tabular-nums">{num(sqlite.sigmaCatalogExpedientes)}</span>
            <br />
            Filas tramitación: <span className="font-mono tabular-nums">{num(sqlite.tramiteRows)}</span>
            <br />
            Enlaces BOCM↔Sigma:{" "}
            <span className="font-mono tabular-nums">{num(sqlite.linkProjectSigma)}</span>
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-100 bg-white/80 px-3 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">JSON visor guardado</p>
          <p className="mt-2 text-xs text-slate-600 leading-relaxed">
            Expedientes en fichero:{" "}
            <span className="font-mono tabular-nums">{num(visorJson.expedientesEnJson)}</span> · Con NTI parseado:{" "}
            <span className="font-mono tabular-nums">{num(visorJson.conArbolNti)}</span>
            <br />
            Generado fichero (UTC): {(visorJson.generatedAt as string) ?? "—"}
          </p>
          {visorStale ? (
            <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-950">
              Mientras corre el fetch, <code>madrid_viso_expedientes.json</code> sólo se reescribe al final del
              lote; el progreso fiable es la barra <strong>Visor fetch (log)</strong>.
            </p>
          ) : null}
        </div>
        <div className="rounded-lg border border-slate-100 bg-white/80 px-3 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Log batch</p>
          <p className="mt-2 text-[11px] text-slate-500">
            {(log?.logPath as string) ?? "—"} · {num(log?.logBytes)} bytes · última escritura UTC:{" "}
            {(log?.logMtime as string) ?? "—"}
            <br />
            Líneas sospechosas (&quot;error&quot; / traceback):{" "}
            <span className={Number(log?.errorLineCount) > 0 ? "font-semibold text-red-700" : ""}>
              {num(log?.errorLineCount)}
            </span>
          </p>
          {log?.errorSample && log.errorSample.length > 0 ? (
            <ul className="mt-2 max-h-24 overflow-y-auto font-mono text-[10px] text-red-900">
              {log.errorSample.map((ln: string, i: number) => (
                <li key={i} className="break-all">
                  {ln}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-medium text-slate-800">
          Últimas líneas del log
        </summary>
        <pre className="mt-2 max-h-56 overflow-auto rounded-lg border border-slate-100 bg-slate-950 px-3 py-2 text-[11px] text-slate-100">
          {(log?.lastLines ?? []).join("\n") || "Sin datos"}
        </pre>
      </details>

      <p className="mt-3 text-[11px] text-slate-500">
        Generado servidor: {(data?.generatedAt as string) ?? "—"} · POC: {(data?.pocRoot as string) ?? ""}
      </p>
    </section>
  );
}
