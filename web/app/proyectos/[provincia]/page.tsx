import Link from "next/link";
import { DirectoryMap } from "@/components/directory/DirectoryMap";
import { DirectoryPlaces } from "@/components/directory/DirectoryPlaces";
import styles from "@/components/directory/Directory.module.css";
import { notFound } from "next/navigation";
import { DirectoryBreadcrumbs } from "@/components/directory/DirectoryNavigation";
import {
  getProjectDirectory,
  municipalityPath,
  provincePath,
} from "@/lib/project-directory";
import { withCanonical } from "@/lib/seo";

type Props = { params: Promise<{ provincia: string }> };

function provinceData(slug: string) {
  const directory = getProjectDirectory();
  const province = directory.provinces.find((p) => p.slug === slug);
  if (!province) notFound();
  return {
    province,
    municipalities: directory.municipalities
      .filter((m) => m.province === slug)
      .sort((a, b) => a.name.localeCompare(b.name, "es")),
  };
}

export async function generateMetadata({ params }: Props) {
  const { province } = provinceData((await params).provincia);
  return withCanonical(provincePath(province.slug), {
    title: `Proyectos urbanísticos en ${province.name}`,
    description: `Consulta los municipios de ${province.name} con planes, actuaciones y proyectos urbanísticos disponibles.`,
  });
}

export default async function ProvincePage({ params }: Props) {
  const { province, municipalities } = provinceData((await params).provincia);
  return (
    <div className={styles.shell}>
      <DirectoryBreadcrumbs
        crumbs={[
          { name: "Inicio", path: "/" },
          { name: "Proyectos", path: "/proyectos" },
          { name: province.name },
        ]}
      />
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.eyebrow}>Territorio · Provincia</span>
          <h1>{province.name}</h1>
          <p>
            Cada municipio cuenta una parte de la historia. Descubre los planes
            y actuaciones que dan forma a {province.name}.
          </p>
          <Link className={styles.heroAction} href="#lugares">
            Explora sus municipios <span>↓</span>
          </Link>
        </div>
        <DirectoryMap
          points={municipalities.map((m) => ({
            name: m.name,
            center: m.center,
            href: municipalityPath(m),
          }))}
          label={`Municipios de ${province.name}`}
        />
      </section>
      <DirectoryPlaces
        title="De cerca, municipio a municipio"
        places={municipalities.map((m) => ({
          name: m.name,
          href: municipalityPath(m),
          caption: province.name,
        }))}
        placeholder="Encuentra un municipio"
      />
    </div>
  );
}
