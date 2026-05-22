import type { Metadata } from "next";
import { Suspense } from "react";
import { BoletinAreaApp } from "@/components/BoletinAreaApp";

export const metadata: Metadata = {
  title: "Boletín de tu área",
  description:
    "Introduce tu dirección y consulta licencias y proyectos de planeamiento recientes en un radio a tu alrededor.",
};

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
