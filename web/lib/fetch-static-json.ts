import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** Origen para /data/* en SSR (evita empaquetar JSON grandes en el bundle serverless). */
export function staticDataOrigin(): string {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return "http://localhost:3000";
}

/**
 * Carga JSON desde public/data vía HTTP en Vercel/producción.
 * En desarrollo local lee del disco si el servidor no está levantado aún.
 */
export async function fetchStaticJson<T>(relFromPublic: string): Promise<T | null> {
  const rel = relFromPublic.startsWith("/") ? relFromPublic : `/${relFromPublic}`;
  const diskPath = join(process.cwd(), "public", rel.replace(/^\//, ""));

  if (process.env.NODE_ENV === "development" && existsSync(diskPath)) {
    try {
      return JSON.parse(readFileSync(diskPath, "utf-8")) as T;
    } catch {
      /* fetch fallback */
    }
  }

  try {
    const url = new URL(rel, staticDataOrigin());
    const res = await fetch(url, { next: { revalidate: 86_400 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    if (existsSync(diskPath)) {
      try {
        return JSON.parse(readFileSync(diskPath, "utf-8")) as T;
      } catch {
        return null;
      }
    }
    return null;
  }
}
