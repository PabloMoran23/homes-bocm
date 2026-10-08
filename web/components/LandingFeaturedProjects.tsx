import Link from "next/link";
import type { FeaturedProject } from "@/lib/landing-featured-projects";

export function LandingFeaturedProjects({ projects }: { projects: FeaturedProject[] }) {
  return <section className="landing-editorial" aria-labelledby="landing-projects-heading">
    <header className="landing-section-heading">
      <div><p className="landing-eyebrow">Selección de Homes</p><h2 id="landing-projects-heading">Proyectos destacados</h2></div>
      <p>Conoce qué se proyecta en cada ámbito, quién lo impulsa y qué documentación está disponible.</p>
    </header>
    {projects.length ? <div className="landing-news-grid">
      {projects.map((item, index) => <article key={item.id} className={index === 0 ? "landing-news-lead" : "landing-news-brief"}>
        <div className="landing-news-meta"><span>{item.municipality}</span><span>{item.category}</span></div>
        <h3><Link href={item.href}>{item.name}</Link></h3>
        <p className="landing-news-body">{item.description}</p>
        <footer><Link href={item.href}>Explorar proyecto <span aria-hidden>↗</span></Link></footer>
      </article>)}
    </div> : <p className="py-8 text-slate-600">Consulta las fichas de proyectos para acceder a la documentación disponible.</p>}
    <div className="landing-news-bottom"><span>Proyectos investigados · Fuentes y documentación en cada ficha</span><Link href="/proyectos">Todos los proyectos ↗</Link></div>
  </section>;
}
