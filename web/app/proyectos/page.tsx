import { DirectoryBreadcrumbs } from "@/components/directory/DirectoryNavigation";
import { ProvinceAtlas } from "@/components/directory/ProvinceAtlas";
import atlasStyles from "@/components/directory/ProvinceAtlas.module.css";
import styles from "@/components/directory/Directory.module.css";
import {
  getProjectDirectory,
  municipalityPath,
  provincePath,
} from "@/lib/project-directory";
import { withCanonical } from "@/lib/seo";
export const metadata = withCanonical("/proyectos", {
  title: "Proyectos urbanísticos por provincia y municipio",
  description:
    "Explora el territorio y descubre planes y actuaciones urbanísticas por municipio.",
});
export default function ProjectsDirectoryPage() {
  const directory = getProjectDirectory();
  const provinces = directory.provinces.map((p) => {
    const municipalities = directory.municipalities.filter(
      (m) => m.province === p.slug,
    );
    return {
      name: p.name,
      slug: p.slug,
      href: provincePath(p.slug),
      municipalities: municipalities.map((m) => ({
        name: m.name,
        href: municipalityPath(m),
      })),
    };
  });
  return (
    <div className={styles.shell}>
      <DirectoryBreadcrumbs
        crumbs={[{ name: "Inicio", path: "/" }, { name: "Proyectos" }]}
      />
      <header className={atlasStyles.heading}>
        <h1>
          El territorio, <em>en transformación.</em>
        </h1>
      </header>
      <ProvinceAtlas provinces={provinces} />
    </div>
  );
}
