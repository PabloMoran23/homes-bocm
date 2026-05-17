import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SigmaExpedienteDetailView } from "@/components/SigmaExpedienteDetailView";
import { loadSigmaFichaBySlug } from "@/lib/load-sigma-ficha";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const ficha = loadSigmaFichaBySlug(slug);
  if (!ficha) return { title: "Proyecto no encontrado" };
  const title =
    ficha.catalog?.EXP_TX_DENOM ||
    ficha.visorCabecera?.h1 ||
    `Proyecto ${ficha.expedienteGrupo}`;
  return {
    title: title.length > 72 ? `${title.slice(0, 69)}…` : title,
    description: `Proyecto urbanístico · Ayto. Madrid · ${ficha.expedienteGrupo}`,
  };
}

export default async function SigmaFichaPage({ params }: PageProps) {
  const { slug } = await params;
  const ficha = loadSigmaFichaBySlug(slug);
  if (!ficha) notFound();

  const metric = getSigmaMetricForGrupo(ficha.expedienteGrupo);
  return <SigmaExpedienteDetailView ficha={ficha} metric={metric} />;
}
