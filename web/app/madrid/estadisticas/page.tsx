import type { Metadata } from "next";
import Link from "next/link";
import { MadridDashboard } from "@/components/madrid/dashboard/MadridDashboard";
import { loadMadridDashboardStats } from "@/lib/load-madrid-dashboard";

/** Evita HTML estático vacío si el JSON no existía en un build anterior. */
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Estadísticas Madrid · Licencias y planeamiento",
  description:
    "Dashboard de licencias urbanísticas y proyectos de planeamiento del Ayuntamiento de Madrid: evolución anual, promotores, usos, trámites y distritos.",
};

export default async function MadridEstadisticasPage() {
  const stats = await loadMadridDashboardStats();

  if (!stats) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <h1 className="text-2xl font-semibold text-slate-900">Estadísticas Madrid</h1>
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

  return (
    <main className="flex-1 bg-slate-100/50">
      <MadridDashboard stats={stats} />
    </main>
  );
}
