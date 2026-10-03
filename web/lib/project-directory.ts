import "server-only";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { projectPath } from "@/lib/project-display";

export type DirectoryProject = {
  id: string;
  aliases: string[];
  title: string;
  municipality: string;
  summary: string;
  type: string;
  status: string;
  researched: boolean;
  group: string;
};
export type DirectoryProvince = { slug: string; name: string };
export type DirectoryMunicipality = {
  slug: string;
  name: string;
  province: string;
  /** Geographic reference of the municipality, not a project location. */
  center: [number, number];
};
type DirectoryData = {
  generatedAt: string;
  provinces: DirectoryProvince[];
  municipalities: DirectoryMunicipality[];
  projects: DirectoryProject[];
};

export const DIRECTORY_PAGE_SIZE = 50;
export const provincePath = (slug: string) => `/proyectos/${slug}`;
export const municipalityPath = (m: DirectoryMunicipality) =>
  `${provincePath(m.province)}/${m.slug}`;
export const directoryPagePath = (m: DirectoryMunicipality, page: number) =>
  `${municipalityPath(m)}${page > 1 ? `?pagina=${page}` : ""}`;

let cached: ReturnType<typeof buildDirectory> | undefined;

function buildDirectory() {
  // Keep the full catalogue on the server, outside public/ and client bundles.
  const data = JSON.parse(
    readFileSync(join(process.cwd(), "data/project-directory.json"), "utf8"),
  ) as DirectoryData;
  const projectsById = new Map(data.projects.map((p) => [p.id, p]));
  for (const project of data.projects) {
    for (const alias of project.aliases) {
      if (!projectsById.has(alias)) projectsById.set(alias, project);
    }
  }
  const projectsByMunicipality = new Map<string, DirectoryProject[]>();
  for (const project of data.projects) {
    const rows = projectsByMunicipality.get(project.municipality) ?? [];
    rows.push(project);
    projectsByMunicipality.set(project.municipality, rows);
  }
  for (const rows of projectsByMunicipality.values()) {
    rows.sort(
      (a, b) =>
        Number(b.researched) - Number(a.researched) ||
        a.title.localeCompare(b.title, "es") ||
        a.id.localeCompare(b.id),
    );
  }
  return { ...data, projectsById, projectsByMunicipality };
}

export function getProjectDirectory() {
  return (cached ??= buildDirectory());
}

export function getDirectoryProject(id: string) {
  return getProjectDirectory().projectsById.get(id);
}

export function getDirectoryMunicipality(
  province: string,
  municipality: string,
) {
  return getProjectDirectory().municipalities.find(
    (m) => m.province === province && m.slug === municipality,
  );
}

export function municipalityProjects(m: DirectoryMunicipality) {
  return (
    getProjectDirectory().projectsByMunicipality.get(
      `${m.province}/${m.slug}`,
    ) ?? []
  );
}

export function projectTerritory(project: DirectoryProject) {
  const [provinceSlug, municipalitySlug] = project.municipality.split("/");
  const municipality = getDirectoryMunicipality(
    provinceSlug,
    municipalitySlug,
  )!;
  const province = getProjectDirectory().provinces.find(
    (p) => p.slug === provinceSlug,
  )!;
  return { province, municipality };
}

export function projectDirectoryCrumbs(project: DirectoryProject) {
  const { province, municipality } = projectTerritory(project);
  return [
    { name: "Inicio", path: "/" },
    { name: "Proyectos", path: "/proyectos" },
    { name: province.name, path: provincePath(province.slug) },
    { name: municipality.name, path: municipalityPath(municipality) },
    { name: project.title },
  ];
}

export function relatedDirectoryProjects(project: DirectoryProject, limit = 6) {
  const peers =
    getProjectDirectory().projectsByMunicipality.get(project.municipality) ??
    [];
  // No proximity inferred from approximate municipal coordinates. Use known context.
  const score = (candidate: DirectoryProject) =>
    (project.group && candidate.group === project.group ? 100 : 0) +
    (project.type && candidate.type === project.type ? 10 : 0) +
    Number(candidate.researched) * 3;
  return peers
    .filter((p) => p.id !== project.id)
    .sort(
      (a, b) =>
        score(b) - score(a) ||
        a.title.localeCompare(b.title, "es") ||
        a.id.localeCompare(b.id),
    )
    .slice(0, limit);
}

export function directoryProjectPath(project: DirectoryProject) {
  return projectPath(project.id);
}

export function parseDirectoryPage(
  value: string | string[] | undefined,
  total: number,
): number | null {
  if (value === undefined) return 1;
  if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) return null;
  const page = Number(value);
  return Number.isSafeInteger(page) &&
    page <= Math.max(1, Math.ceil(total / DIRECTORY_PAGE_SIZE))
    ? page
    : null;
}
