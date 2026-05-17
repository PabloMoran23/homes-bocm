import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { UbicacionDetailView } from "@/components/UbicacionDetailView";
import { loadUbicacionFicha } from "@/lib/load-ubicacion";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";

type Props = { params: Promise<{ ndp: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ndp } = await params;
  const ficha = await loadUbicacionFicha(ndp);
  if (!ficha) return { title: "Ubicación no encontrada" };
  return {
    title: ficha.inmueble.direccion || `NDP ${ndp}`,
    description: `Licencias y expedientes urbanísticos en ${ficha.inmueble.distrito || "Madrid"}.`,
  };
}

export default async function UbicacionPage({ params }: Props) {
  const { ndp } = await params;
  const ficha = await loadUbicacionFicha(ndp);
  if (!ficha) notFound();

  const metricsByExpediente: Record<string, ReturnType<typeof getSigmaMetricForGrupo>> = {};
  for (const exp of ficha.expedientesSigma) {
    metricsByExpediente[exp.expediente_grupo] = getSigmaMetricForGrupo(exp.expediente_grupo);
  }

  return <UbicacionDetailView ficha={ficha} metricsByExpediente={metricsByExpediente} />;
}
