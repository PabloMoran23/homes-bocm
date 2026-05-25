import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { headers } from "next/headers";
import { getSiteUrl } from "@/lib/site-url";

/** Origen para /data/* cuando el fichero no está en el deployment (fallback HTTP). */
export function staticDataOrigin(): string {
  return getSiteUrl();
}

async function requestOrigin(): Promise<string | null> {
  try {
    const h = await headers();
    const host = h.get("x-forwarded-host") ?? h.get("host");
    if (!host) return null;
    const proto = h.get("x-forwarded-proto") ?? "https";
    return `${proto}://${host}`;
  } catch {
    return null;
  }
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
 * 2) HTTP al mismo host de la petición (runtime serverless en Vercel).
 */
export async function fetchStaticJson<T>(relFromPublic: string): Promise<T | null> {
  const rel = relFromPublic.startsWith("/") ? relFromPublic : `/${relFromPublic}`;

  for (const diskPath of diskCandidates(rel)) {
    const fromDisk = readDiskJson<T>(diskPath);
    if (fromDisk) return fromDisk;
  }

  const origins = [await requestOrigin(), staticDataOrigin()].filter(
    (o, i, a): o is string => Boolean(o) && a.indexOf(o) === i,
  );

  for (const origin of origins) {
    try {
      const url = new URL(rel, origin);
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) continue;
      return (await res.json()) as T;
    } catch {
      /* siguiente origen */
    }
  }

  return null;
}
