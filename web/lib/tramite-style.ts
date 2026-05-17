/** Estilo visual por tipo de trámite (visor Ayto. Madrid). */

export function tramiteKind(tramite: string | null | undefined): string {
  const t = (tramite || "").toLowerCase();
  if (t.includes("definitiv")) return "definitiva";
  if (t.includes("provisional") || t.includes("propuesta")) return "provisional";
  if (t.includes("inicial")) return "inicial";
  if (t.includes("boletín") || t.includes("boletin") || t.includes("publicación"))
    return "boletin";
  if (t.includes("información") || t.includes("informacion")) return "info";
  return "otro";
}

export function tramiteDotClass(kind: string): string {
  switch (kind) {
    case "definitiva":
      return "bg-emerald-500 ring-emerald-200";
    case "inicial":
      return "bg-sky-500 ring-sky-200";
    case "provisional":
      return "bg-violet-500 ring-violet-200";
    case "boletin":
      return "bg-amber-500 ring-amber-200";
    case "info":
      return "bg-cyan-500 ring-cyan-200";
    default:
      return "bg-slate-400 ring-slate-200";
  }
}

export function tramiteBadgeClass(kind: string): string {
  switch (kind) {
    case "definitiva":
      return "bg-emerald-50 text-emerald-900 ring-emerald-200";
    case "inicial":
      return "bg-sky-50 text-sky-900 ring-sky-200";
    case "provisional":
      return "bg-violet-50 text-violet-900 ring-violet-200";
    case "boletin":
      return "bg-amber-50 text-amber-950 ring-amber-200";
    case "info":
      return "bg-cyan-50 text-cyan-950 ring-cyan-200";
    default:
      return "bg-slate-100 text-slate-700 ring-slate-200";
  }
}
