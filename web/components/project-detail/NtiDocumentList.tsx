"use client";

import { useMemo, useState } from "react";
import type { SigmaNtiLinkedGrupo } from "@/lib/sigma-nti-linked";
import { formatBytes } from "@/lib/sigma-nti-linked";
import type { SigmaVisorNtiDoc } from "@/lib/types";
import { hasValue } from "@/lib/project-display";

type DocRow = {
  key: string;
  titulo: string;
  url: string;
  rutaCarpetas: string | null;
  tipodocNti: string | null;
  localPath: string | null;
  fileBytes: number | null;
  downloadError: string | null;
};

function ntiAssetHref(localPath: string): string {
  return `/api/nti-asset?path=${encodeURIComponent(localPath)}`;
}

function mergeDocs(
  linked: SigmaNtiLinkedGrupo | null,
  muestra: SigmaVisorNtiDoc[] | undefined,
): DocRow[] {
  if (linked?.documentos?.length) {
    return linked.documentos.map((d, i) => ({
      key: `${d.url}-${i}`,
      titulo: d.titulo || d.tooltip || "Documento",
      url: d.url,
      rutaCarpetas: d.rutaCarpetas,
      tipodocNti: d.tipodocNti,
      localPath: d.localPath,
      fileBytes: d.fileBytes,
      downloadError: d.downloadError,
    }));
  }
  return (muestra ?? []).map((d, i) => ({
    key: `${d.url}-${i}`,
    titulo: d.titulo || d.tooltip || "Documento",
    url: d.url,
    rutaCarpetas: d.rutaCarpetas || null,
    tipodocNti: d.tipodocNti,
    localPath: null,
    fileBytes: null,
    downloadError: null,
  }));
}

export function NtiDocumentList({
  linked,
  muestra,
  totalVisor,
  listadoUrl,
}: {
  linked: SigmaNtiLinkedGrupo | null;
  muestra?: SigmaVisorNtiDoc[];
  totalVisor?: number | null;
  listadoUrl?: string | null;
}) {
  const [q, setQ] = useState("");
  const docs = useMemo(() => mergeDocs(linked, muestra), [linked, muestra]);
  const stats = linked?.stats;

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return docs;
    return docs.filter(
      (d) =>
        d.titulo.toLowerCase().includes(needle) ||
        (d.rutaCarpetas || "").toLowerCase().includes(needle) ||
        (d.tipodocNti || "").toLowerCase().includes(needle),
    );
  }, [docs, q]);

  if (!docs.length && !totalVisor) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        {stats ? (
          <>
            <StatPill label="Indexados" value={String(stats.total)} />
            <StatPill label="En disco" value={String(stats.downloaded)} accent />
            {stats.errors > 0 ? (
              <StatPill label="Errores" value={String(stats.errors)} warn />
            ) : null}
            {stats.bytesTotal > 0 ? (
              <StatPill label="Volumen" value={formatBytes(stats.bytesTotal)} />
            ) : null}
          </>
        ) : totalVisor ? (
          <StatPill label="PDF en árbol NTI" value={String(totalVisor)} />
        ) : null}
      </div>

      {docs.length > 8 ? (
        <label className="block">
          <span className="sr-only">Buscar documento</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por título, carpeta o tipo…"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </label>
      ) : null}

      <ul className="max-h-[min(52vh,520px)] divide-y divide-slate-100 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/50">
        {filtered.length === 0 ? (
          <li className="px-4 py-8 text-center text-sm text-slate-500">Sin coincidencias</li>
        ) : (
          filtered.map((d) => <NtiRow key={d.key} doc={d} />)
        )}
      </ul>

      {totalVisor && docs.length < totalVisor && !linked ? (
        <p className="text-xs text-slate-500">
          Mostrando {docs.length} de {totalVisor} documentos del visor.
          {hasValue(listadoUrl) ? (
            <>
              {" "}
              <a
                href={listadoUrl!}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-teal-700 underline"
              >
                Ver listado completo en el Ayuntamiento
              </a>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}

function StatPill({
  label,
  value,
  accent,
  warn,
}: {
  label: string;
  value: string;
  accent?: boolean;
  warn?: boolean;
}) {
  const cls = warn
    ? "bg-red-50 text-red-900 ring-red-200"
    : accent
      ? "bg-teal-50 text-teal-950 ring-teal-200"
      : "bg-white text-slate-800 ring-slate-200";
  return (
    <div className={`rounded-lg px-3 py-2 ring-1 ${cls}`}>
      <div className="text-[10px] font-semibold uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-sm font-bold tabular-nums">{value}</div>
    </div>
  );
}

function NtiRow({ doc }: { doc: DocRow }) {
  const local = doc.localPath?.trim();
  const href = local ? ntiAssetHref(local) : doc.url;
  const isLocal = Boolean(local);

  return (
    <li className="group bg-white px-4 py-3 transition hover:bg-teal-50/30">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-teal-900 hover:underline"
        >
          {doc.titulo}
        </a>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          {isLocal ? (
            <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-emerald-900">
              Local
            </span>
          ) : null}
          {doc.tipodocNti ? (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
              {doc.tipodocNti}
            </span>
          ) : null}
          {doc.fileBytes ? (
            <span className="text-[10px] tabular-nums text-slate-400">
              {formatBytes(doc.fileBytes)}
            </span>
          ) : null}
        </div>
      </div>
      {doc.rutaCarpetas ? (
        <p className="mt-1 truncate text-[11px] text-slate-500" title={doc.rutaCarpetas}>
          {doc.rutaCarpetas}
        </p>
      ) : null}
      {doc.downloadError ? (
        <p className="mt-1 text-[11px] text-red-700">{doc.downloadError}</p>
      ) : null}
    </li>
  );
}
