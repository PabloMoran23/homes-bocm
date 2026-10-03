import Link from "next/link";
import { DirectoryMap } from "@/components/directory/DirectoryMap";
import styles from "@/components/directory/Directory.module.css";
import { notFound, permanentRedirect } from "next/navigation";
import {
  DirectoryBreadcrumbs,
  DirectoryFeaturedProjects,
  DirectoryPagination,
  DirectoryProjectCards,
} from "@/components/directory/DirectoryNavigation";
import {
  DIRECTORY_PAGE_SIZE,
  directoryPagePath,
  getDirectoryMunicipality,
  getProjectDirectory,
  municipalityPath,
  municipalityProjects,
  parseDirectoryPage,
  provincePath,
} from "@/lib/project-directory";
import { withCanonical } from "@/lib/seo";

type Props = {
  params: Promise<{ provincia: string; municipio: string }>;
  searchParams: Promise<{ pagina?: string | string[] }>;
};

async function pageData({ params, searchParams }: Props) {
  const { provincia, municipio } = await params;
  const municipality = getDirectoryMunicipality(provincia, municipio);
  if (!municipality) notFound();
  const projects = municipalityProjects(municipality);
  const { pagina } = await searchParams;
  const page = parseDirectoryPage(pagina, projects.length);
  if (page === null) notFound();
  if (pagina === "1") permanentRedirect(municipalityPath(municipality));
  const province = getProjectDirectory().provinces.find(
    (p) => p.slug === provincia,
  )!;
  return { municipality, province, projects, page };
}

export async function generateMetadata(props: Props) {
  const { municipality, page } = await pageData(props);
  return withCanonical(directoryPagePath(municipality, page), {
    title: `Proyectos urbanísticos en ${municipality.name}${page > 1 ? ` · Página ${page}` : ""}`,
    description: `Planes y actuaciones en ${municipality.name}. Consulta sus características y documentación.${page > 1 ? ` Página ${page}.` : ""}`,
  });
}

export default async function MunicipalityPage(props: Props) {
  const { municipality, province, projects, page } = await pageData(props);
  const start = (page - 1) * DIRECTORY_PAGE_SIZE;
  const visible = projects.slice(start, start + DIRECTORY_PAGE_SIZE);
  const featured =
    page === 1 ? visible.filter((p) => p.researched).slice(0, 2) : [];
  const list = visible.filter((p) => !featured.includes(p));
  return (
    <div className={styles.shell}>
      <DirectoryBreadcrumbs
        crumbs={[
          { name: "Inicio", path: "/" },
          { name: "Proyectos", path: "/proyectos" },
          { name: province.name, path: provincePath(province.slug) },
          { name: municipality.name },
        ]}
      />
      <section className={styles.hero}>
        <div className={`${styles.heroCopy} ${styles.heroCopyWide}`}>
          <span className={styles.eyebrow}>{province.name} · Municipio</span>
          <h1>{municipality.name}</h1>
          <p>
            Una mirada al urbanismo de {municipality.name}. Explora sus planes,
            conoce las actuaciones y accede a la información que explica cómo
            evoluciona el municipio.
          </p>
          <Link className={styles.heroAction} href="#actuaciones">
            Descubre qué está pasando <span>↓</span>
          </Link>
        </div>
        <DirectoryMap
          local
          points={[{ name: municipality.name, center: municipality.center }]}
          label="Referencia del municipio · No ubica actuaciones"
        />
      </section>
      <div id="actuaciones">
        <DirectoryFeaturedProjects projects={featured} />
        {list.length > 0 && (
          <section className={styles.catalogue}>
            <div>
              <div className={styles.sectionHeading}>
                <div>
                  <span className={styles.eyebrow}>
                    Planeamiento y desarrollo
                  </span>
                  <h2>Planes y actuaciones</h2>
                </div>
              </div>
              <DirectoryProjectCards projects={list} headingLevel={3} />
            </div>
            <aside className={styles.catalogueAside}>
              <span className={styles.eyebrow}>Sobre este lugar</span>
              <h3>Entender {municipality.name}</h3>
              <p>
                La información reúne planeamiento y documentos públicos. Cada
                actuación conserva sus fuentes para que puedas ampliar el
                contexto.
              </p>
              <div className={styles.asideNote}>
                Los análisis de Homes ofrecen una lectura más completa de las
                actuaciones investigadas.
              </div>
              <Link href={provincePath(province.slug)}>
                Explora {province.name} <span>↗</span>
              </Link>
              <Link href="/proyectos">
                Volver al atlas <span>↗</span>
              </Link>
            </aside>
          </section>
        )}
        <DirectoryPagination
          municipality={municipality}
          total={projects.length}
          page={page}
        />
      </div>
    </div>
  );
}
