import type { Metadata } from "next";
import { ExploreMadridApp } from "@/components/ExploreMadridApp";

export const metadata: Metadata = {
  title: "Mapa Madrid",
  description:
    "Mapa unificado: proyectos urbanísticos del Ayuntamiento y ubicaciones con licencias.",
};

export default function ExplorePage() {
  return (
    <div className="fixed inset-x-0 bottom-0 top-14 z-0 overflow-hidden">
      <ExploreMadridApp />
    </div>
  );
}
