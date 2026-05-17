import type { Metadata } from "next";
import { ExploreMadridApp } from "@/components/ExploreMadridApp";

export const metadata: Metadata = {
  title: "Mapa Madrid",
  description:
    "Mapa unificado: expedientes SIGMA del Ayuntamiento y ubicaciones con licencias urbanísticas.",
};

export default function ExplorePage() {
  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-[480px] flex-col">
      <ExploreMadridApp />
    </div>
  );
}
