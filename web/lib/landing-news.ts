import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export type LandingNewsSpotlight = {
  id: string;
  href: string;
  tag: string;
  dateLabel: string;
  title: string;
  dek: string;
  featured?: boolean;
  numViviendas?: number;
  expedienteGrupo?: string;
};

export type LandingNewsFile = {
  generatedAt: string;
  source?: string;
  criteria?: string;
  items: LandingNewsSpotlight[];
};

const FALLBACK: LandingNewsSpotlight[] = [
  {
    id: "fallback-explore",
    featured: true,
    href: "/explore",
    tag: "Madrid",
    dateLabel: "Explorar",
    title: "Descubre qué se está planeando cerca de ti",
    dek: "Mapa unificado de proyectos urbanísticos y licencias por dirección.",
  },
];

let cached: LandingNewsFile | null = null;

export function loadLandingNews(): LandingNewsFile {
  if (cached) return cached;
  const path = join(process.cwd(), "public/data/landing-news.json");
  if (!existsSync(path)) {
    cached = {
      generatedAt: new Date().toISOString(),
      items: FALLBACK,
    };
    return cached;
  }
  try {
    cached = JSON.parse(readFileSync(path, "utf-8")) as LandingNewsFile;
    if (!cached.items?.length) cached.items = FALLBACK;
    return cached;
  } catch {
    cached = { generatedAt: new Date().toISOString(), items: FALLBACK };
    return cached;
  }
}
