import type { MetadataRoute } from "next";
import { isPublicEdition } from "@/lib/edition";
import { projectPath } from "@/lib/project-display";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import { getSiteUrl } from "@/lib/site-url";
import projects from "@/public/data/sitemap-projects.json";

const PUBLIC_PAGES: {
  path: string;
  changeFrequency: MetadataRoute.Sitemap[0]["changeFrequency"];
  priority: number;
}[] = [
  { path: "/", changeFrequency: "weekly", priority: 1 },
  { path: "/explore", changeFrequency: "weekly", priority: 0.9 },
  { path: "/boletin", changeFrequency: "weekly", priority: 0.9 },
  { path: "/madrid/estadisticas", changeFrequency: "weekly", priority: 0.8 },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  if (!isPublicEdition()) return [];

  const base = getSiteUrl();

  const staticEntries: MetadataRoute.Sitemap = PUBLIC_PAGES.map(
    ({ path, changeFrequency, priority }) => ({
      url: `${base}${path}`,
      changeFrequency,
      priority,
    }),
  );

  // Refresh this snapshot with db/export_sitemap_projects.py after new research.
  const projectEntries: MetadataRoute.Sitemap = projects.map((project) => ({
    url: `${base}${/^\d+\/\d+\/\d+/.test(project.proyectoId)
      ? sigmaFichaPath(project.proyectoId)
      : projectPath(project.proyectoId)}`,
    lastModified: project.investigadoAt,
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  return [...staticEntries, ...projectEntries];
}
