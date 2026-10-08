import "server-only";
import { loadProyectosInvestigados } from "@/lib/load-madrid-presentacion";
import { projectPath } from "@/lib/project-display";
import { getProjectDirectory } from "@/lib/project-directory";

export type FeaturedProject = {
  id: string;
  name: string;
  municipality: string;
  category: string;
  description: string;
  href: string;
};

// Editorial selection of researched developments. Consultation dates and internal
// findings do not determine prominence or become project headlines.
const SELECTION = [
  {
    id: "135/2018/00489",
    name: "Madrid Nuevo Norte",
    category: "Transformación urbana",
    description: "La operación urbanística que reorganiza el entorno de Chamartín y la prolongación de la Castellana. Consulta el ámbito, el programa residencial y la documentación de planeamiento reunida en la investigación.",
  },
  {
    id: "bocm:bocm-2022-11-18-18-c25d88f8fb5df2ce",
    name: "Nuevo San Luis",
    category: "Desarrollo residencial",
    description: "Regeneración de suelo urbano en Hortaleza con vivienda libre y protegida, zonas verdes y equipamientos. La ficha recoge el programa, los promotores y los instrumentos de gestión del ámbito.",
  },
  {
    id: "bocm:bocm-2025-02-24-26-003606afed090329",
    name: "Paseo de la Ermita del Santo",
    category: "Regeneración urbana",
    description: "Transformación de un ámbito junto a Madrid Río, en el distrito de Latina, con vivienda, zonas verdes y equipamientos. Explora la ordenación prevista y los hitos documentados de su tramitación.",
  },
];

export async function loadLandingFeaturedProjects(): Promise<FeaturedProject[]> {
  const projects = await loadProyectosInvestigados();
  const directory = getProjectDirectory();
  return SELECTION.flatMap(item => {
    const project = projects.find(project => project.proyectoId === item.id);
    if (!project) return [];
    const record = directory.projectsById.get(item.id)
      ?? directory.projectsById.get(item.id.replace(/^bocm:/, ""));
    return [{
      ...item,
      municipality: project.municipio || "",
      href: projectPath(record?.id ?? item.id),
    }];
  });
}
