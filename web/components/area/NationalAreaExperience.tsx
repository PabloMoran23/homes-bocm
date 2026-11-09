"use client";

import { LaunchWaitlistSection } from "@/components/LaunchWaitlistSection";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import type { NationalAreaProject, NationalAreaResult } from "@/lib/national-area";
import type { AreaProject } from "@/lib/area-context";

const MiniMap = dynamic(() => import("@/components/BoletinMiniMap").then(m => m.BoletinMiniMap), { ssr:false, loading:() => <p className="area-map-placeholder">Cargando mapa del entorno…</p> });
const dateLabel = (date:string) => new Date(`${date}T12:00:00Z`).toLocaleDateString("es-ES",{day:"numeric",month:"short",year:"numeric",timeZone:"Europe/Madrid"});

function NationalProjectCard({project, nearby = false}: {project:NationalAreaProject; nearby?:boolean}) {
  const summary = project.summary.length > 320 ? project.summary.slice(0,project.summary.lastIndexOf(" ",320)) + "…" : project.summary;
  return <article className="area-project-card" id={`national-project-${encodeURIComponent(project.id)}`}>
    <p className="area-instrument">{nearby ? project.containsPoint ? "El ámbito incluye esta dirección" : `A ${project.distanceM?.toLocaleString("es-ES")} m del ámbito` : "En el municipio · sin proximidad atribuida"}</p>
    <h3 className="line-clamp-3"><Link href={project.href} title={project.title}>{project.title}</Link></h3>
    {summary && <p className="area-project-summary">{summary}</p>}
    {project.phase && <div className="area-phase"><span>Estado o clasificación del catálogo</span><strong>{project.phase}</strong></div>}
    {project.date && <p className="area-detail-note">Fecha del registro: <time dateTime={project.date}>{dateLabel(project.date)}</time></p>}
    <div className="area-card-actions"><Link href={project.href}>Entender el proyecto y consultar sus fuentes ↗</Link></div>
  </article>;
}
export function NationalAreaExperience({data}:{data:NationalAreaResult}) {
  const [historyOpen,setHistoryOpen] = useState(false);
  const [nearbyVisible,setNearbyVisible] = useState(3);
  const [recentVisible,setRecentVisible] = useState(3);
  const [selected,setSelected] = useState<string|null>(null);
  const mapProjects:AreaProject[] = data.nearby.flatMap(p => p.geometry ? [{ id:p.id, group:p.id, href:p.href, title:p.title, summary:p.summary, phase:p.phase, instrument:"Proyecto", researched:p.researched, scope:"local" as const, distanceM:p.distanceM || 0, containsPoint:Boolean(p.containsPoint), location:[data.center.lng,data.center.lat] as [number,number], geometry:p.geometry, milestones:[], lastMilestone:null, recent:false, sourceUrl:null }] : []);
  if (data.scope === "uncovered") return <section className="area-experience" aria-label="Cobertura de la zona"><header className="area-place-heading"><div><p className="area-eyebrow">Información disponible</p><h1>{data.center.label}</h1></div></header><div className="area-framework"><h3>Todavía no podemos ofrecer una lectura de esta zona</h3><p>No hemos podido vincular esta dirección a un municipio con información en nuestro catálogo. Esto no significa que no haya proyectos ni obras.</p>{data.alternatives.length > 0 && <><p>Puedes explorar otros municipios próximos con información:</p><ul>{data.alternatives.map(m => <li key={m.href}><Link href={m.href}>{m.name} ↗</Link></li>)}</ul></>}</div></section>;
  const nearbyIds = new Set(data.nearby.map(p => p.id));
  const municipalRecent = data.recent.filter(p => !p.geometry);
  return <section className="area-experience" aria-label="Información del entorno">
    <header className="area-place-heading"><div><p className="area-eyebrow">{data.scope === "nearby" ? `Proyectos cercanos y contexto de ${data.municipality!.name}` : "Una lectura de tu municipio"}</p><h1>{data.municipality!.name}</h1><p>{data.center.label}</p></div><Link className="area-outline-link" href={data.municipality!.href}>Todos los proyectos del municipio ↗</Link></header>
    <div className="area-reading-note"><span aria-hidden="true">↳</span><p>{data.scope === "nearby" ? `Los proyectos cercanos tienen una ubicación identificada dentro de ${data.radiusM} m. El resto de la información corresponde al conjunto del municipio.` : "Mostramos información del conjunto del municipio. No tenemos ubicaciones suficientemente precisas para atribuir estos proyectos a tu calle o al radio seleccionado."} La cobertura depende de las fuentes disponibles; no es un censo de obras y licencias.</p></div>
    {data.total === 0 && <p className="area-summary-note">La consulta no ha devuelto fichas para esta dirección o municipio. No significa que no haya actuaciones; puedes revisar el directorio y sus fuentes.</p>}
    {!data.recent.length && data.total > 0 && <p className="area-summary-note">No disponemos de novedades fechadas para este periodo en las fuentes consultadas. Mostramos los antecedentes y el catálogo disponible; esto no implica que no haya actividad reciente.</p>}
    {data.liveUnavailable && <p className="area-inline-notice">No se pudo actualizar la consulta municipal. Mostramos el catálogo disponible{data.catalogueDate ? ` del ${dateLabel(data.catalogueDate.slice(0,10))}` : ""}; las fichas enlazan sus fuentes.</p>}
    <div className={data.nearby.length ? "area-workspace" : "area-national-workspace"}>
      <div className="area-main">
        {data.nearby.length > 0 && <section className="area-section"><header className="area-section-heading"><div><p className="area-eyebrow">Con ubicación identificada</p><h3>Proyectos y planes del entorno</h3></div></header><div className="area-project-grid">{data.nearby.slice(0,nearbyVisible).map(p => <NationalProjectCard key={p.id} project={p} nearby />)}</div>{data.nearby.length > nearbyVisible && <button type="button" className="area-load-more" onClick={() => setNearbyVisible(v => v+3)}>Ver más proyectos cercanos</button>}</section>}
        {municipalRecent.length > 0 && <section className="area-section"><header className="area-section-heading"><div><p className="area-eyebrow">En todo el municipio</p><h3>Registros de los últimos {data.months} meses</h3></div></header><p className="area-section-intro">Propuestas, planeamiento y actuaciones con una fecha documentada en las fuentes consultadas. La fecha de un registro no acredita el inicio de obras.</p><div className="area-project-grid">{municipalRecent.slice(0,recentVisible).map(p => <NationalProjectCard key={p.id} project={p} />)}</div>{municipalRecent.length > recentVisible && <button type="button" className="area-load-more" onClick={() => setRecentVisible(v => v+3)}>Ver más registros del municipio</button>}</section>}
        {data.history.some(p => !nearbyIds.has(p.id)) && <section className="area-section"><header className="area-section-heading"><div><p className="area-eyebrow">El contexto del municipio</p><h3>Planes y antecedentes que ayudan a entenderlo</h3></div>{!historyOpen && <button type="button" className="area-text-link" onClick={() => setHistoryOpen(true)}>Ver más antecedentes ↗</button>}</header><p className="area-section-intro">{data.recent.length < 3 ? "Ampliamos la mirada con registros anteriores y fichas sin fecha precisa. " : ""}Estos expedientes aportan contexto; su presencia no confirma que estén en ejecución.</p><div className="area-project-grid">{data.history.filter(p => !nearbyIds.has(p.id)).slice(0,historyOpen ? 12 : 3).map(p => <NationalProjectCard key={p.id} project={p} />)}</div></section>}
        {data.municipality && <Link className="area-outline-link" href={data.municipality.href}>Explorar todo lo que tenemos de {data.municipality.name} ↗</Link>}
        <p className="area-sources">Fuentes y documentos disponibles en cada ficha. Las fechas de revisión del catálogo no se presentan como novedades de los proyectos. Solo mostramos licencias por tipo cuando disponemos de datos adecuados para esa consulta.</p>
      </div>
      {data.nearby.length > 0 && <aside className="area-map-column" aria-label="Mapa de proyectos cercanos"><div className="area-map-heading"><div><p className="area-eyebrow">Ubicaciones identificadas</p><h3>El entorno de tu dirección</h3></div><span>{data.radiusM} m</span></div><MiniMap lat={data.center.lat} lng={data.center.lng} radiusM={data.radiusM} licencias={[]} expedientesSigma={[]} projects={mapProjects} overview showLicenseLegend={false} selectedProject={selected} onProjectSelect={group => { setSelected(group); setNearbyVisible(data.nearby.length); requestAnimationFrame(() => document.getElementById(`national-project-${encodeURIComponent(group)}`)?.scrollIntoView({behavior:"smooth",block:"nearest"})); }} /><p className="area-map-explainer">Contornos orientativos y ubicaciones de proyectos. Los expedientes sin una ubicación identificada se consultan en la sección municipal.</p><LaunchWaitlistSection source="boletin" compact /></aside>}
    </div>
  </section>;
}
