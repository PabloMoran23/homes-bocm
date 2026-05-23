import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** Origen para /data/* cuando el fichero no está en el deployment (fallback HTTP). */
export function staticDataOrigin(): string {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return "http://localhost:3000";
}

function readDiskJson<T>(diskPath: string): T | null {
  if (!existsSync(diskPath)) return null;
  try {
    return JSON.parse(readFileSync(diskPath, "utf-8")) as T;
  } catch {
    return null;
  }
}

/**
 * Carga JSON desde public/data.
 * En Vercel/producción prioriza lectura del disco (public/ va en el deployment).
 * El fetch HTTP queda como fallback si el fichero no está en el bundle.
 */
export async function fetchStaticJson<T>(relFromPublic: string): Promise<T | null> {
  const rel = relFromPublic.startsWith("/") ? relFromPublic : `/${relFromPublic}`;
  const diskPath = join(process.cwd(), "public", rel.replace(/^\//, ""));

  const fromDisk = readDiskJson<T>(diskPath);
  if (fromDisk) return fromDisk;

  try {
    const url = new URL(rel, staticDataOrigin());
    const res = await fetch(url, { next: { revalidate: 86_400 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
