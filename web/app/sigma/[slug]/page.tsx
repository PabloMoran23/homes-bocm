import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SigmaExpedienteDetailView } from "@/components/SigmaExpedienteDetailView";
import { loadSigmaFichaBySlug } from "@/lib/load-sigma-ficha";
import { getSigmaMetricForGrupo } from "@/lib/load-sigma-metrics";
import { sigmaPickDisplayHeadline } from "@/lib/sigma-presentation";
import { sigmaFaseShortLabel } from "@/lib/sigma-user-labels";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const ficha = await loadSigmaFichaBySlug(slug);
  if (!ficha) return { title: "Proyecto no encontrado" };
  const { title } = sigmaPickDisplayHeadline({
    expedienteGrupo: ficha.expedienteGrupo,
    source: ficha.catalog?.source,
    denominacion: ficha.catalog?.EXP_TX_DENOM,
    visorH1: ficha.visorCabecera?.h1,
    visorH2: ficha.visorCabecera?.h2,
    fase: ficha.catalog?.FAS_TX_DENOM,
    figEtiq: ficha.catalog?.FIG_TX_ETIQ,
    tfigAbrev: ficha.catalog?.TFIG_TX_ABREV,
    organo: ficha.catalog?.ORG_TX_DESC,
  });
  return {
    title: title.length > 72 ? `${title.slice(0, 69)}…` : title,
    description: [
      "Proyecto urbanístico en Madrid",
      sigmaFaseShortLabel(ficha.catalog?.FAS_TX_DENOM),
    ].filter(Boolean).join(" · "),
  };
}

export default async function SigmaFichaPage({ params }: PageProps) {
  const { slug } = await params;
  const ficha = await loadSigmaFichaBySlug(slug);
  if (!ficha) notFound();

  const metric = await getSigmaMetricForGrupo(ficha.expedienteGrupo);
  return <SigmaExpedienteDetailView ficha={ficha} metric={metric} />;
}
