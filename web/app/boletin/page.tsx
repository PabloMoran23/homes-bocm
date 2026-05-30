import type { Metadata } from "next";
import { Suspense } from "react";
import { BoletinAreaApp } from "@/components/BoletinAreaApp";
import { withCanonical } from "@/lib/seo";

export const metadata: Metadata = withCanonical("/boletin", {
  title: "Qué ocurre en tu zona — licencias y proyectos cerca de tu dirección",
  description:
    "Introduce tu dirección en Madrid capital y consulta licencias de obra y proyectos de planeamiento recientes en un radio a tu alrededor.",
});

export default function BoletinPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100dvh-3.5rem)] items-center justify-center bg-[#f8f6f1] text-sm text-slate-500">
          Cargando boletín…
        </div>
      }
    >
      <BoletinAreaApp />
    </Suspense>
  );
}
