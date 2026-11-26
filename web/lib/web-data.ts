/**
 * Web data files (/data/*) live in Supabase Storage, bucket `web-data`:
 *   manifest.json            live release: { version, files: { name → { path, sha256, bytes } } }
 *   objects/<sha256>.<ext>   immutable file bodies
 *
 * Edge-safe (used by middleware): no node:* imports. Nothing here queries
 * Postgres; every read goes to the Storage CDN.
 */

export const WEB_DATA_BUCKET = "web-data";

/** How long a server instance trusts its copy of the manifest. */
export const MANIFEST_TTL_SECONDS = 600;

export type WebDataFile = {
  path: string;
  sha256: string;
  bytes: number;
  contentType?: string;
};

export type WebDataManifest = {
  version: string;
  publishedAt: string;
  files: Record<string, WebDataFile>;
};

export function webDataStorageBase(): string | null {
  // Full base override (tests, or a custom CDN domain in front of the bucket).
  const override = process.env.WEB_DATA_STORAGE_URL?.trim().replace(/\/$/, "");
  if (override) return override;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim().replace(/\/$/, "");
  return url ? `${url}/storage/v1/object/public/${WEB_DATA_BUCKET}` : null;
}

/**
 * Local public/data/ wins in development unless WEB_DATA_SOURCE=storage, so
 * `npm run build-data` output shows up without publishing.
 */
export function webDataUsesStorage(): boolean {
  const mode = process.env.WEB_DATA_SOURCE;
  if (mode === "local") return false;
  if (mode === "storage") return webDataStorageBase() !== null;
  return process.env.NODE_ENV === "production" && webDataStorageBase() !== null;
}

let cached: { at: number; manifest: WebDataManifest | null } | null = null;
let inflight: Promise<WebDataManifest | null> | null = null;

async function loadManifest(base: string): Promise<WebDataManifest | null> {
  try {
    const res = await fetch(`${base}/manifest.json`, {
      next: { revalidate: MANIFEST_TTL_SECONDS, tags: ["web-data-manifest"] },
    } as RequestInit);
    if (!res.ok) return null;
    const m = (await res.json()) as WebDataManifest;
    return m && typeof m.files === "object" ? m : null;
  } catch {
    return null;
  }
}

/**
 * Live manifest, memoised per instance for MANIFEST_TTL_SECONDS. On a failed
 * refresh the previous manifest stays in use.
 */
export async function getWebDataManifest(): Promise<WebDataManifest | null> {
  const base = webDataStorageBase();
  if (!base) return null;
  const now = Date.now();
  if (cached && now - cached.at < MANIFEST_TTL_SECONDS * 1000) return cached.manifest;
  if (!inflight) {
    inflight = loadManifest(base)
      .then((m) => {
        cached = { at: Date.now(), manifest: m ?? cached?.manifest ?? null };
        return cached.manifest;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

/** "/data/foo.json" or "foo.json" → "foo.json"; null for nested or odd paths. */
export function webDataName(pathOrName: string): string | null {
  const name = pathOrName.replace(/^\/?(data\/)?/, "");
  return /^[A-Za-z0-9._-]+$/.test(name) ? name : null;
}

/** Immutable Storage URL of the live version of `name`, or null. */
export async function webDataObjectUrl(pathOrName: string): Promise<string | null> {
  const name = webDataName(pathOrName);
  const base = webDataStorageBase();
  if (!name || !base) return null;
  const manifest = await getWebDataManifest();
  const file = manifest?.files[name];
  return file ? `${base}/${file.path}` : null;
}
