import type { Metadata } from "next";
import { ExploreMadridApp } from "@/components/ExploreMadridApp";
import { ExplorePageSeoPanel } from "@/components/seo/ExplorePageSeo";
import { withCanonical } from "@/lib/seo";

export const metadata: Metadata = withCanonical("/explore", {
  title: "Mapa de urbanismo Madrid: licencias y planes",
  description:
    "Mapa de licencias de obra, planeamiento y proyectos urbanísticos en Madrid capital.",
});

export default function ExplorePage() {
  return (
    <div className="fixed inset-x-0 top-14 z-0 h-[calc(100dvh-3.5rem-var(--site-footer-compact))] overflow-hidden">
      <ExploreMadridApp />
      <ExplorePageSeoPanel />
    </div>
  );
}
