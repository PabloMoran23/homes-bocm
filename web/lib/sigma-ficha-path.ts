import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";

/** Slug URL-safe: `135/2021/00618` → `135-2021-00618` */
export function sigmaFichaSlug(grupoOrVariant: string): string {
  return expedienteGrupoKeyFromVariant(grupoOrVariant).replace(/\//g, "-");
}

/** Inverso del slug (distrito/año/número con 5 dígitos). */
export function sigmaFichaGrupoFromSlug(slug: string): string {
  const s = decodeURIComponent(slug).trim();
  const parts = s.split("-").filter(Boolean);
  if (parts.length >= 3 && /^\d+$/.test(parts[0]) && /^\d+$/.test(parts[1])) {
    return `${parts[0]}/${parts[1]}/${parts[2].padStart(5, "0")}`;
  }
  return s.replace(/-/g, "/");
}

export function sigmaFichaPath(grupoOrVariant: string): string {
  return `/proyecto/${encodeURIComponent(sigmaFichaSlug(grupoOrVariant))}`;
}
