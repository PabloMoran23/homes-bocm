import type { Project } from "./types";

function escCell(v: string) {
  const s = v.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function projectsToCsv(rows: Project[]): string {
  const header = [
    "sourceId",
    "sourceLabel",
    "territorioId",
    "territorioLabel",
    "bocmDate",
    "artNum",
    "municipio",
    "tipoInstrumento",
    "estadoTramitacion",
    "nombreSector",
    "fechaAcuerdo",
    "organo",
    "promotor",
    "numViviendas",
    "supTotalM2",
    "supEdificableM2",
    "tipoVivienda",
    "categoriasTematicas",
    "economicoResumen",
    "importeTotalEur",
    "procedimientoTipo",
    "procedimientoExpediente",
    "title",
    "resumen",
    "pdfUrl",
  ];
  const lines = [header.join(",")];
  for (const p of rows) {
    lines.push(
      [
        p.sourceId,
        p.sourceLabel,
        p.territorioId,
        p.territorioLabel,
        p.bocmDate,
        p.artNum,
        p.municipio,
        p.tipoInstrumento,
        p.estadoTramitacion,
        p.nombreSector,
        p.fechaAcuerdo ?? "",
        p.organo,
        p.promotor ?? "",
        p.numViviendas ?? "",
        p.supTotalM2 ?? "",
        p.supEdificableM2 ?? "",
        p.tipoVivienda ?? "",
        p.categoriasTematicas ?? "",
        p.economicoResumen ?? "",
        p.importeTotalEur ?? "",
        p.procedimientoTipo ?? "",
        p.procedimientoExpediente ?? "",
        p.title,
        p.resumen,
        p.pdfUrl ?? "",
      ]
        .map((c) => escCell(String(c)))
        .join(","),
    );
  }
  return lines.join("\n");
}
