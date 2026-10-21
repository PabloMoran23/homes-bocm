import { unstable_cache } from "next/cache";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import { rpcDominio } from "@/lib/dominio-cache";
import type { MadridPresentacion, ProyectoInvestigado } from "@/lib/madrid-presentacion";

export async function loadMadridPresentacion(): Promise<MadridPresentacion | null> {
  return fetchStaticJson<MadridPresentacion>("/data/madrid-presentacion.json");
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function asText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

const loadCachedProyectosInvestigados = unstable_cache(
  async (): Promise<unknown> => {
    const { data, error, missing } = await rpcDominio<unknown>("list_proyectos_investigados");
    if (missing) throw new Error("supabase-missing");
    if (error || data == null) return null;
    return data;
  },
  ["list-proyectos-investigados-v1"],
  { revalidate: 600 },
);

export async function loadProyectosInvestigados(): Promise<ProyectoInvestigado[]> {
  let data: unknown;
  try {
    data = await loadCachedProyectosInvestigados();
  } catch {
    return [];
  }
  if (data == null) return [];
  let rows: unknown = data;
  if (typeof rows === "string") {
    try {
      rows = JSON.parse(rows) as unknown;
    } catch {
      return [];
    }
  }
  if (!Array.isArray(rows)) return [];
  const out: ProyectoInvestigado[] = [];
  for (const raw of rows) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const proyectoId = asText(row.proyectoId);
    const resumen = asText(row.resumen);
    if (!proyectoId || !resumen) continue;
    out.push({
      proyectoId,
      municipio: asText(row.municipio),
      denominacion: asText(row.denominacion) ?? proyectoId,
      nombrePublico: asText(row.nombrePublico),
      resumen,
      estado: asText(row.estado) ?? "parcial",
      viviendas: asNumber(row.viviendas),
      superficieM2: asNumber(row.superficieM2),
      promotor: asText(row.promotor),
    });
  }
  return out;
}
