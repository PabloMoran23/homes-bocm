import type { MetadataRoute } from "next";
import { isPublicEdition } from "@/lib/edition";
import { projectPath } from "@/lib/project-display";
import { sigmaFichaPath } from "@/lib/sigma-ficha-path";
import { getSiteUrl } from "@/lib/site-url";
import { fetchStaticJson } from "@/lib/fetch-static-json";

type SitemapProject = { proyectoId: string; investigadoAt?: string };

// The project list comes from the live web data release, not the bundle.
export const revalidate = 86400;

const PUBLIC_PAGES: {
  path: string;
  changeFrequency: MetadataRoute.Sitemap[0]["changeFrequency"];
  priority: number;
}[] = [
  { path: "/", changeFrequency: "weekly", priority: 1 },
  { path: "/proyectos", changeFrequency: "weekly", priority: 0.9 },
  { path: "/explore", changeFrequency: "weekly", priority: 0.9 },
  { path: "/boletin", changeFrequency: "weekly", priority: 0.9 },
  { path: "/madrid/estadisticas", changeFrequency: "weekly", priority: 0.8 },
];

const DEFAULT_PROJECT_LIMIT = 5000;

/** Tope de fichas en el sitemap (SITEMAP_PROJECT_LIMIT, por defecto 5000). */
function projectLimit(): number {
  const raw = process.env.SITEMAP_PROJECT_LIMIT?.trim();
  if (!raw) return DEFAULT_PROJECT_LIMIT;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : DEFAULT_PROJECT_LIMIT;
}

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

  // Snapshot ordenado por calidad (y fecha) con db/export_sitemap_projects.py;
  // aquí solo se aplica el tope, así que la BD no se consulta al servir el sitemap.
  const projects = (await fetchStaticJson<SitemapProject[]>("/data/sitemap-projects.json")) ?? [];
  const projectEntries: MetadataRoute.Sitemap = projects
    .slice(0, projectLimit())
    .map((project) => ({
      url: `${base}${/^\d+\/\d+\/\d+/.test(project.proyectoId)
        ? sigmaFichaPath(project.proyectoId)
        : projectPath(project.proyectoId)}`,
      lastModified: project.investigadoAt,
      changeFrequency: "monthly",
      priority: 0.6,
    }));

  return [...staticEntries, ...projectEntries];
}
