import type { ProyectoInfoDato } from "./proyecto-info-extra";

/** Event dates come from the event text, never from the source's publication date. */
export function proyectoHitoFecha(dato: ProyectoInfoDato): { label: string; year: number | null } {
  const text = dato.valor;
  const written = text.match(/\b(\d{1,2}\s+de\s+)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+((?:19|20)\d{2})\b/i);
  if (written) return { label: written[0], year: Number(written[3]) };
  const iso = text.match(/\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b/);
  if (iso) return { label: `${iso[3]}/${iso[2]}/${iso[1]}`, year: Number(iso[1]) };
  const numeric = text.match(/\b(\d{1,2})[-/](\d{1,2})[-/]((?:19|20)\d{2})\b/);
  if (numeric) return { label: `${numeric[1]}/${numeric[2]}/${numeric[3]}`, year: Number(numeric[3]) };
  const year = text.match(/\b(?:19|20)\d{2}\b/);
  return year ? { label: year[0], year: Number(year[0]) } : { label: "Fecha no especificada", year: null };
}
