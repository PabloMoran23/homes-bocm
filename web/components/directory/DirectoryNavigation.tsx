import styles from "./Directory.module.css";
import Link from "next/link";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbJsonLd } from "@/lib/json-ld";
import {
  type DirectoryProject,
  type DirectoryMunicipality,
  directoryProjectPath,
  DIRECTORY_PAGE_SIZE,
  directoryPagePath,
  municipalityPath,
  projectDirectoryCrumbs,
  projectTerritory,
  relatedDirectoryProjects,
} from "@/lib/project-directory";

// Excerpts are plain text; research summaries may contain Markdown emphasis.
function excerpt(value: string) {
  return value
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\*\*|__|`/g, "");
}

export const directoryLinkClass =
  "font-medium text-[var(--portal-accent)] underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4";

export function DirectoryBreadcrumbs({
  crumbs,
}: {
  crumbs: { name: string; path?: string }[];
}) {
  return (
    <nav aria-label="Ruta de navegación" className={styles.breadcrumbs}>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {crumbs.map((crumb, i) => (
          <li
            key={`${i}-${crumb.name}`}
            className="flex min-w-0 max-w-full items-center gap-2"
          >
            {i > 0 ? (
              <span aria-hidden="true" className="text-slate-400">
                /
              </span>
            ) : null}
            {crumb.path ? (
              <Link href={crumb.path} className={directoryLinkClass}>
                {crumb.name}
              </Link>
            ) : (
              <span aria-current="page" className="line-clamp-1 max-w-xl">
                {crumb.name}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function DirectoryProjectCards({
  projects,
  headingLevel = 2,
}: {
  projects: DirectoryProject[];
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <ul className={styles.projectList}>
      {projects.map((project) => (
        <li key={project.id}>
          <Link
            prefetch={false}
            href={directoryProjectPath(project)}
            className={styles.projectRow}
          >
            <span className={styles.projectGlyph} aria-hidden="true">
              ↗
            </span>
            <div>
              <div className={styles.projectMeta}>
                {project.researched
                  ? "Análisis de Homes"
                  : project.type || "Planeamiento urbano"}
              </div>
              <Heading>{project.title}</Heading>
              {project.summary && <p>{excerpt(project.summary)}</p>}
            </div>
            <span className={styles.rowArrow} aria-hidden="true">
              →
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
export function DirectoryFeaturedProjects({
  projects,
}: {
  projects: DirectoryProject[];
}) {
  if (!projects.length) return null;
  return (
    <section className={styles.featuredSection}>
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>La mirada de Homes</span>
          <h2>En detalle</h2>
        </div>
      </div>
      <ul className={styles.featuredGrid}>
        {projects.map((project) => (
          <li className={styles.featureCard} key={project.id}>
            <Link prefetch={false} href={directoryProjectPath(project)}>
              <div className={styles.featureTop}>
                <span>Análisis de Homes</span>
                <span aria-hidden="true">↗</span>
              </div>
              <h3>{project.title}</h3>
              {project.summary && <p>{excerpt(project.summary)}</p>}
              <div className={styles.featureLink}>
                Explorar actuación <span aria-hidden="true">→</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function DirectoryPagination({
  municipality,
  total,
  page,
}: {
  municipality: DirectoryMunicipality;
  total: number;
  page: number;
}) {
  const pages = Math.ceil(total / DIRECTORY_PAGE_SIZE);
  if (pages <= 1) return null;
  return (
    <nav aria-label="Páginas de proyectos" className={styles.pagination}>
      <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
        {page > 1 ? (
          <Link
            prefetch={false}
            className={directoryLinkClass}
            href={directoryPagePath(municipality, page - 1)}
          >
            ← Anterior
          </Link>
        ) : (
          <span />
        )}
        <span>
          Página {page} de {pages}
        </span>
        {page < pages ? (
          <Link
            prefetch={false}
            className={directoryLinkClass}
            href={directoryPagePath(municipality, page + 1)}
          >
            Siguiente →
          </Link>
        ) : (
          <span />
        )}
      </div>
      <details className={styles.pageChoices}>
        <summary className="cursor-pointer text-[var(--portal-accent)]">
          Ir a una página
        </summary>
        <div className="mt-3 flex flex-wrap gap-2">
          {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
            <Link
              prefetch={false}
              key={n}
              aria-label={`Página ${n}`}
              aria-current={n === page ? "page" : undefined}
              href={directoryPagePath(municipality, n)}
              className={`min-w-9 rounded-md px-3 py-2 text-center ${n === page ? "bg-[var(--portal-accent)] text-white" : "bg-[var(--portal-paper)] text-[var(--portal-accent)] hover:underline"}`}
            >
              {n}
            </Link>
          ))}
        </div>
      </details>
    </nav>
  );
}

export function ProjectTerritoryNavigation({
  project,
}: {
  project: DirectoryProject;
}) {
  const crumbs = projectDirectoryCrumbs(project);
  return (
    <div className="mx-auto w-full max-w-6xl px-4 pt-6 sm:px-6">
      <JsonLd data={breadcrumbJsonLd(directoryProjectPath(project), crumbs)} />
      <DirectoryBreadcrumbs crumbs={crumbs} />
    </div>
  );
}

export function RelatedDirectoryProjects({
  project,
}: {
  project: DirectoryProject;
}) {
  const { municipality } = projectTerritory(project);
  const related = relatedDirectoryProjects(project);
  return (
    <section
      aria-label="Otros proyectos del municipio"
      className="mx-auto w-full max-w-6xl px-4 pb-12 pt-6 sm:px-6"
    >
      <div className={styles.sectionHeading}>
        <h2 className="text-xl font-semibold">
          Sigue explorando {municipality.name}
        </h2>
        <Link
          href={municipalityPath(municipality)}
          className={`text-sm ${directoryLinkClass}`}
        >
          Explorar el municipio →
        </Link>
      </div>
      {related.length ? (
        <DirectoryProjectCards projects={related} headingLevel={3} />
      ) : (
        <p className="text-sm text-slate-600">
          Consulta el directorio para explorar otros municipios de la provincia.
        </p>
      )}
    </section>
  );
}
