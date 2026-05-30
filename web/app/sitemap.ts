import type { MetadataRoute } from "next";
import { isPublicEdition } from "@/lib/edition";
import { listSigmaFichaSlugs } from "@/lib/load-sigma-ficha";
import { getSiteUrl } from "@/lib/site-url";

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
  const now = new Date();

  const staticEntries: MetadataRoute.Sitemap = PUBLIC_PAGES.map(
    ({ path, changeFrequency, priority }) => ({
      url: `${base}${path}`,
      lastModified: now,
      changeFrequency,
      priority,
    }),
  );

  const slugs = await listSigmaFichaSlugs();
  const projectEntries: MetadataRoute.Sitemap = slugs.map((slug) => ({
    url: `${base}/proyecto/${encodeURIComponent(slug)}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  return [...staticEntries, ...projectEntries];
}
