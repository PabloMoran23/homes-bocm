import Link from "next/link";
import { LandingMunicipioSearch } from "@/components/LandingMunicipioSearch";
import { LandingDashboardSection } from "@/components/LandingDashboardSection";
import { LandingMapBackground } from "@/components/LandingMapBackground";
import { LandingFeaturedProjects } from "@/components/LandingFeaturedProjects";
import { LandingTuZonaSection } from "@/components/LandingTuZonaSection";
import { loadLandingFeaturedProjects } from "@/lib/landing-featured-projects";
import { loadMadridDashboardStats } from "@/lib/load-madrid-dashboard";

function titleCaseDistrito(name: string): string {
  const lower = name.toLowerCase().replace(/_/g, " ");
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export default async function Home() {
  const [featuredProjects, dashboardStats] = await Promise.all([loadLandingFeaturedProjects(), loadMadridDashboardStats()]);

  const planesCount = dashboardStats?.sigma?.total;
  const licenciasCount = dashboardStats?.licencias?.totalRows;
  const latestLicenciasYear = dashboardStats?.licencias?.seriesByYear?.at(-1);
  const topDistritos = dashboardStats?.licencias?.topDistrito?.slice(0, 3) ?? [];

  return (
    <main className="flex-1">
      <section className="landing-search-hero">
        <div className="landing-search-map" aria-hidden="true" inert>
          <LandingMapBackground />
        </div>
        <div className="landing-search-wash" aria-hidden="true" />
        <div className="landing-search-content">
          <p className="mb-5 text-xs font-medium uppercase tracking-[.22em] text-[var(--portal-accent)]">Información urbanística para empresas</p>
          <h1>Información para decidir<br />dónde invertir.</h1>
          <p className="landing-hero-description">Proyectos, planeamiento y actividad urbanística.<br className="hidden sm:block" /> Investiga el territorio con información documentada.</p>
          <LandingMunicipioSearch />
          <Link href="/explore" className="mt-8 inline-block text-xs font-medium text-[var(--portal-accent)] underline underline-offset-4">Explorar el mapa</Link>
        </div>
        <div className="landing-map-credit">© OpenStreetMap · © OpenMapTiles</div>
        <div className="landing-search-caption"><span>Obras · Planeamiento · Proyectos</span><span>Explora lo que cambia ↓</span></div>
      </section>

      <LandingFeaturedProjects projects={featuredProjects} />

      <LandingTuZonaSection />

      <LandingDashboardSection
        planesCount={planesCount}
        licenciasCount={licenciasCount}
        latestLicenciasYear={latestLicenciasYear?.year}
        latestLicenciasTotal={latestLicenciasYear?.total}
        topDistritos={topDistritos.map((d) => ({
          name: titleCaseDistrito(d.name),
          count: d.count,
        }))}
      />

      <section className="landing-business" aria-labelledby="landing-business-heading">
        <header className="landing-section-heading"><div><p className="landing-eyebrow">Homes para profesionales</p><h2 id="landing-business-heading">Del territorio<br />a tu mesa de trabajo.</h2></div><p>Una base documental para los equipos que estudian, desarrollan y transforman el suelo.</p></header>
        <div className="landing-business-grid">
          {[
            { number: "01", name: "Inversión y suelo", text: "Estudia ámbitos de desarrollo, consulta su tramitación y reúne contexto antes de valorar una oportunidad.", action: "Explorar municipios", href: "/explore", tags: "Localización / Planeamiento" },
            { number: "02", name: "Promoción y construcción", text: "Identifica actuaciones y consulta el programa, los promotores y la documentación disponible de cada proyecto.", action: "Consultar proyectos", href: "/proyectos", tags: "Proyectos / Actores" },
            { number: "03", name: "Consultoría y arquitectura", text: "Prepara estudios de entorno con expedientes, referencias y fuentes que puedas revisar con tu equipo.", action: "Analizar una zona", href: "/boletin", tags: "Entorno / Documentación" },
          ].map(item => <article key={item.number}><span className="landing-business-number">{item.number}</span><p className="landing-business-tags">{item.tags}</p><h3>{item.name}</h3><p>{item.text}</p><Link href={item.href}>{item.action} ↗</Link></article>)}
        </div>
        <div className="landing-business-contact"><div><h3>¿Qué necesita investigar tu equipo?</h3><p>Cuéntanos en qué territorios trabajáis y qué información necesitáis.</p></div><a href="mailto:info@homes-urbanismo.es">Hablemos de tu proyecto ↗</a></div>
      </section>

    </main>
  );
}
