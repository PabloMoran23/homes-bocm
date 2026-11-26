import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { getSiteUrl } from "@/lib/site-url";
import { getWebDataManifest, webDataName, webDataObjectUrl } from "@/lib/web-data";

/** Origen para /data/* cuando no hay Storage configurado (fallback HTTP). */
export function staticDataOrigin(): string {
  return getSiteUrl();
}

function readDiskJson<T>(diskPath: string): T | null {
  if (!existsSync(diskPath)) return null;
  try {
    return JSON.parse(readFileSync(diskPath, "utf-8")) as T;
  } catch {
    return null;
  }
}

function diskCandidates(relFromPublic: string): string[] {
  const rel = relFromPublic.replace(/^\//, "");
  const cwd = process.cwd();
  return [join(cwd, "public", rel), join(cwd, "web", "public", rel)];
}

/**
 * Parsed bodies of immutable Storage objects, per server instance. Only files
 * up to MEMO_MAX_BYTES: Next's data cache skips bodies over 2 MB, and the big
 * GeoJSON layers would cost too much memory to keep.
 */
const MEMO_MAX_BYTES = 8 * 1024 * 1024;
const MEMO_MAX_ENTRIES = 16;
const memo = new Map<string, unknown>();

function remember(url: string, value: unknown) {
  if (memo.size >= MEMO_MAX_ENTRIES) memo.delete(memo.keys().next().value as string);
  memo.set(url, value);
}

async function fetchStorageJson<T>(rel: string): Promise<T | null | undefined> {
  const url = await webDataObjectUrl(rel);
  if (!url) return undefined;
  if (memo.has(url)) return memo.get(url) as T;
  try {
    // Object URLs are content-addressed: cache them forever.
    const res = await fetch(url, { cache: "force-cache" });
    if (!res.ok) return null;
    const value = (await res.json()) as T;
    const name = webDataName(rel);
    const bytes = name ? (await getWebDataManifest())?.files[name]?.bytes ?? Infinity : Infinity;
    if (bytes <= MEMO_MAX_BYTES) remember(url, value);
    return value;
  } catch {
    return null;
  }
}

/**
 * Carga JSON de /data/*.
 * 1) Disco (desarrollo y CI, tras `npm run build-data` o `npm run pull-data`).
 * 2) Supabase Storage, release vivo según manifest.json (producción).
 * 3) HTTP al origen público, si Storage no está configurado.
 * No usa headers(): eso marcaba la página como dinámica.
 */
export async function fetchStaticJson<T>(relFromPublic: string): Promise<T | null> {
  const rel = relFromPublic.startsWith("/") ? relFromPublic : `/${relFromPublic}`;

  for (const diskPath of diskCandidates(rel)) {
    const fromDisk = readDiskJson<T>(diskPath);
    if (fromDisk) return fromDisk;
  }

  const fromStorage = await fetchStorageJson<T>(rel);
  if (fromStorage !== undefined) return fromStorage;

  try {
    const url = new URL(rel, staticDataOrigin());
    const res = await fetch(url, { next: { revalidate: 600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
