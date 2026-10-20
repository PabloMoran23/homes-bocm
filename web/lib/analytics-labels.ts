import "server-only";
import {
  getDirectoryMunicipality,
  getDirectoryProject,
  getProjectDirectory,
} from "@/lib/project-directory";
import { SECTION_LABELS, SOURCE_LABELS, type AnalyticsSection, type AnalyticsSource } from "@/lib/analytics-filters";

const PATH_TITLES: Record<string, string> = {
  "/": "Inicio",
  "/explore": "Mapa",
  "/boletin": "Tu zona",
  "/madrid/estadisticas": "Estadísticas de Madrid",
  "/proyectos": "Directorio de proyectos",
  "/ubicacion": "Ficha de ubicación",
  "/admin/analitica": "Analítica",
  "/admin/login": "Acceso interno",
};

const EVENT_LABELS: Record<string, string> = {
  page_view: "Página vista",
  page_engagement: "Actividad en página",
  document_click: "Documento",
  outbound_click: "Enlace externo",
  boletin_buscar: "Búsqueda en tu zona",
  estadisticas_filtro: "Filtro de estadísticas",
  mapa_buscar: "Búsqueda en el mapa",
  mapa_seleccionar: "Selección en el mapa",
  ficha_proyecto_ver: "Consulta de ficha",
  ficha_pestana: "Sección de ficha",
};

export function labelAnalyticsSource(source: string): string {
  return SOURCE_LABELS[source as AnalyticsSource] ?? source;
}

export function labelAnalyticsSection(section: string): string {
  return SECTION_LABELS[section as AnalyticsSection] ?? section;
}

export function labelAnalyticsEvent(name: string): string {
  return EVENT_LABELS[name] ?? name;
}

export function labelAnalyticsPath(path: string): { label: string; href: string } {
  const href = path.startsWith("/") ? path : "/";
  const known = PATH_TITLES[path];
  if (known) return { label: known, href };
  if (path.startsWith("/proyecto/")) {
    const raw = path.slice("/proyecto/".length);
    const id = safeDecode(raw);
    try {
      const title = getDirectoryProject(id)?.title;
      if (title) return { label: title, href };
    } catch {
      /* Directory file is optional for a readable fallback. */
    }
    return { label: id || path, href };
  }
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "proyectos" && parts[1]) {
    try {
      const directory = getProjectDirectory();
      const province = directory.provinces.find((item) => item.slug === parts[1]);
      if (parts.length === 2) {
        return { label: province ? `Proyectos en ${province.name}` : path, href };
      }
      const municipality = getDirectoryMunicipality(parts[1], parts[2] ?? "");
      if (municipality) {
        return { label: province ? `${municipality.name} (${province.name})` : municipality.name, href };
      }
    } catch {
      return { label: path, href };
    }
  }
  if (path.startsWith("/madrid/")) return { label: "Estadísticas de Madrid", href };
  if (path.startsWith("/admin/")) return { label: "Administración", href };
  return { label: path, href };
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
