import type { Metadata } from "next";
import Link from "next/link";
import { MadridPresentacion } from "@/components/madrid/dashboard/MadridPresentacion";
import { MadridDashboard } from "@/components/madrid/dashboard/MadridDashboard";
import { JsonLd } from "@/components/seo/JsonLd";
import { madridDatasetJsonLd } from "@/lib/json-ld";
import { loadMadridDashboardStats } from "@/lib/load-madrid-dashboard";
import { loadMadridPresentacion, loadProyectosInvestigados } from "@/lib/load-madrid-presentacion";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import type { EspanaPresentacion } from "@/lib/madrid-presentacion";
import type { DataSummary } from "@/lib/types";
import { withCanonical } from "@/lib/seo";

/** Evita HTML estático vacío si el JSON no existía en un build anterior. */
export const dynamic = "force-dynamic";

export const metadata: Metadata = withCanonical("/madrid/estadisticas", {
  title: "Estadísticas de licencias urbanísticas en Madrid por distrito",
  description:
    "El panorama urbanístico de Madrid y de España: obra, locales, planes en marcha y los grandes desarrollos de la capital.",
});

const INSTRUMENTO_FAMILIA: [RegExp, string][] = [
  [/plan especial/i, "Plan especial"],
  [/estudio de detalle/i, "Estudio de detalle"],
  [/plan parcial/i, "Plan parcial"],
  [/urbanizaci[oó]n/i, "Proyecto de urbanización"],
  [/normas subsidiarias/i, "Normas subsidiarias"],
  [/modificaci/i, "Modificación del plan"],
  [/plan general|^pgou$/i, "Plan general"],
  [/convenio/i, "Convenio urbanístico"],
  [/reparcel/i, "Reparcelación"],
  [/suelo r[uú]stico/i, "Suelo rústico"],
  [/licencia/i, "Licencia"],
];

function familiaInstrumento(name: string): string | null {
  if (/^sin clasificar$/i.test(name) || /^otro$/i.test(name)) return null;
  for (const [pattern, label] of INSTRUMENTO_FAMILIA) {
    if (pattern.test(name)) return label;
  }
  return null;
}

function espanaFromSummary(summary: DataSummary | null): EspanaPresentacion | null {
  if (!summary) return null;
  const porAno = summary.byYear
    .map((row) => ({ year: Number(row.year), count: row.count }))
    .filter((row) => row.year >= 1990 && row.year <= 2030)
    .sort((a, b) => a.year - b.year);
  const relevant = summary.byTerritorioRelevant ?? summary.byTerritorio ?? [];
  const territorios = relevant.filter((row) => row.count >= 30);
  const territoriosMenores = relevant.filter((row) => row.count > 0 && row.count < 30);
  const instrumentoMap = new Map<string, number>();
  for (const row of summary.byTipo ?? []) {
    const familia = familiaInstrumento(row.name);
    if (!familia) continue;
    instrumentoMap.set(familia, (instrumentoMap.get(familia) ?? 0) + row.count);
  }
  const instrumentos = [...instrumentoMap.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);
  const municipios = (summary.byMunicipio ?? [])
    .filter((row) => row.name.toLowerCase() !== "madrid")
    .slice(0, 8);
  return {
    anuncios: summary.totalRelevant ?? summary.total,
    yearMin: porAno[0] ? String(porAno[0].year) : null,
    yearMax: porAno.at(-1) ? String(porAno.at(-1)!.year) : null,
    comunidades: summary.byTerritorio?.length ?? territorios.length,
    territorios,
    territoriosMenores,
    instrumentos,
    municipios,
    porAno,
  };
}

export default async function MadridEstadisticasPage() {
  const [stats, presentacion, summaryFile, proyectos] = await Promise.all([
    loadMadridDashboardStats(),
    loadMadridPresentacion(),
    fetchStaticJson<DataSummary>("/data/summary.json"),
    loadProyectosInvestigados(),
  ]);

  if (!stats && !presentacion) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard Madrid</h1>
        <p className="mt-4 text-slate-600">
          Aún no hay datos agregados. Genera el fichero con{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-sm">npm run build-data</code>{" "}
          en la carpeta <code className="rounded bg-slate-100 px-1.5 py-0.5 text-sm">web</code>.
        </p>
        <Link
          href="/explore"
          className="mt-6 inline-block text-sm font-medium text-[var(--portal-accent)] hover:underline"
        >
          Volver a explorar
        </Link>
      </main>
    );
  }

  const espana = espanaFromSummary(summaryFile);

  return (
    <main className="flex-1 bg-[var(--portal-paper)]">
      {stats ? <JsonLd data={madridDatasetJsonLd(stats)} /> : null}
      {presentacion ? (
        <MadridPresentacion data={presentacion} espana={espana} proyectos={proyectos} />
      ) : stats ? (
        <MadridDashboard stats={stats} />
      ) : null}
    </main>
  );
}
