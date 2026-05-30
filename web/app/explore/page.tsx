import type { Metadata } from "next";
import { ExploreMadridApp } from "@/components/ExploreMadridApp";
import { withCanonical } from "@/lib/seo";

export const metadata: Metadata = withCanonical("/explore", {
  title: "Mapa de urbanismo Madrid: licencias, SIGMA y BOCM",
  description:
    "Mapa unificado de licencias urbanísticas, proyectos de planeamiento SIGMA y anuncios BOCM en Madrid capital.",
});

export default function ExplorePage() {
  return (
    <div className="fixed inset-x-0 top-14 z-0 h-[calc(100dvh-3.5rem)] overflow-hidden">
      <ExploreMadridApp />
    </div>
  );
}
