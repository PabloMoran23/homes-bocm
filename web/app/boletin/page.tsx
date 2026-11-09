import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { BoletinAreaApp } from "@/components/BoletinAreaApp";
import { JsonLd } from "@/components/seo/JsonLd";
import { BoletinPageSeoFaq } from "@/components/seo/BoletinPageSeo";
import { faqPageJsonLd } from "@/lib/json-ld";
import { BOLETIN_FAQ } from "@/lib/seo-faq-content";
import { withCanonical } from "@/lib/seo";

export const metadata: Metadata = withCanonical("/boletin", {
  title: "Qué ocurre en tu zona — licencias y proyectos cerca de tu dirección",
  description:
    "Explora proyectos, expedientes, cambios documentados y el marco urbanístico de una dirección o municipio en España, según las fuentes disponibles. Detalle de licencias en Madrid capital.",
});

export default async function BoletinPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const params = await searchParams;
  if (params.edit !== "1" && (typeof params.q === "string" || typeof params.ndp === "string")) {
    const query = new URLSearchParams();
    for (const key of ["q","ndp","lat","lng","localidad","radiusM","months"]) if (typeof params[key] === "string") query.set(key,params[key]);
    redirect(`/boletin/resultados?${query}`);
  }
  return (
    <>
      <JsonLd data={faqPageJsonLd("/boletin", BOLETIN_FAQ)} />
      <Suspense
        fallback={
          <div className="flex min-h-[calc(100dvh-3.5rem)] items-center justify-center bg-[#f8f6f1] text-sm text-slate-500">
            Cargando boletín…
          </div>
        }
      >
        <BoletinAreaApp />
      </Suspense>
      <BoletinPageSeoFaq />
    </>
  );
}
