import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { UbicacionDetailView } from "@/components/UbicacionDetailView";
import { getSigmaClasificacionForGrupo } from "@/lib/load-sigma-clasificacion";
import { getSigmaProgramasForExpedientes } from "@/lib/load-sigma-programas";
import { loadUbicacionFicha } from "@/lib/load-ubicacion";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";
import type { SigmaClassification } from "@/lib/sigma-classification";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import { withCanonical } from "@/lib/seo";

type Props = { params: Promise<{ ndp: string }> };

function ubicacionPath(ndp: string): string {
  return `/ubicacion/${encodeURIComponent(ndp)}`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ndp } = await params;
  const path = ubicacionPath(ndp);
  const ficha = await loadUbicacionFicha(ndp);
  if (!ficha) return withCanonical(path, { title: "Ubicación no encontrada" });
  return withCanonical(path, {
    title: ficha.inmueble.direccion || `NDP ${ndp}`,
    description: `Actividad urbanística y proyectos cercanos en ${ficha.inmueble.distrito || "Madrid"}.`,
  });
}

export default async function UbicacionPage({ params }: Props) {
  const { ndp } = await params;
  const ficha = await loadUbicacionFicha(ndp);
  if (!ficha) notFound();

  const metricsByExpediente: Record<string, SigmaExpedienteMetric | null> = {};
  const clasificacionByExpediente: Record<string, SigmaClassification | null> = {};
  await Promise.all(
    ficha.expedientesSigma.map(async (exp) => {
      const grupo = exp.expediente_grupo;
      const [metric, clasificacion] = await Promise.all([
        getSigmaMetricForGrupo(grupo),
        getSigmaClasificacionForGrupo(grupo),
      ]);
      metricsByExpediente[grupo] = metric;
      clasificacionByExpediente[grupo] = clasificacion;
    }),
  );

  const grupos = ficha.expedientesSigma.map((exp) => exp.expediente_grupo);
  const { programas: programasEnZona, sueltos: expedientesSueltos } =
    await getSigmaProgramasForExpedientes(grupos);

  return (
    <UbicacionDetailView
      ficha={ficha}
      metricsByExpediente={metricsByExpediente}
      clasificacionByExpediente={clasificacionByExpediente}
      programasEnZona={programasEnZona}
      expedientesSueltos={expedientesSueltos}
    />
  );
}
