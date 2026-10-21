import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { getSiteUrl } from "@/lib/site-url";

/** Origen para /data/* cuando el fichero no está en el deployment (fallback HTTP). */
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
  return [
    join(cwd, "public", rel),
    join(cwd, "web", "public", rel),
  ];
}

/**
 * Carga JSON desde public/data.
 * 1) Disco (build local / Vercel build con fichero en repo).
 * 2) HTTP al origen público. No usa headers(): eso marcaba la página como dinámica.
 */
export async function fetchStaticJson<T>(relFromPublic: string): Promise<T | null> {
  const rel = relFromPublic.startsWith("/") ? relFromPublic : `/${relFromPublic}`;

  for (const diskPath of diskCandidates(rel)) {
    const fromDisk = readDiskJson<T>(diskPath);
    if (fromDisk) return fromDisk;
  }

  try {
    const url = new URL(rel, staticDataOrigin());
    const res = await fetch(url, { next: { revalidate: 600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
