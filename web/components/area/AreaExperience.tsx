"use client";

import { LaunchWaitlistSection } from "@/components/LaunchWaitlistSection";

import { hasBroadMapExtent } from "@/lib/map-project-scope";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { LicenciaTitulo } from "@/components/LicenciaTitulo";
import { licenciaTituloDesdeTipo } from "@/lib/ubicacion-resumen";
import { areaDate, areaToday, areaCutoff, areaPhaseHint, enrichAreaProject, type AreaContext, type AreaProject, type AreaProjectDetail } from "@/lib/area-context";
import type { MonthlyLicenseSummary } from "@/lib/area-monthly";
import { boletinStatLabel, type BoletinAreaResult, type BoletinEvento } from "@/lib/boletin-area";

const BoletinMiniMap = dynamic(() => import("@/components/BoletinMiniMap").then(module => module.BoletinMiniMap), { ssr: false, loading: () => <div className="area-map-placeholder">Cargando mapa del entorno…</div> });
const AreaProjectExpansion = dynamic(() => import("./AreaProjectExpansion").then(module => module.AreaProjectExpansion), { loading: () => <p className="area-loading">Cargando ficha del proyecto…</p> });
type Tab = "resumen" | "proyectos" | "cambios" | "licencias";
const dateLabel = (date: string) => new Date(`${date}T12:00:00Z`).toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric", timeZone: "Europe/Madrid" });
const distanceLabel = (project: AreaProject) => project.containsPoint ? "Tu dirección está dentro del ámbito" : `A ${project.distanceM.toLocaleString("es-ES")} m del ámbito`;
export const areaProjectElementId = (group: string) => `area-project-${group.replace(/[^\w-]/g, "-")}`;

function ProjectCard({ project, number, selected, onSelect, preview, onDetail }: { project: AreaProject; number: number; selected: boolean; onSelect: () => void; preview: boolean; onDetail: (group: string, detail: AreaProjectDetail) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [live, setLive] = useState<AreaProjectDetail | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const id = useId();
  useEffect(() => {
    if (!preview) return;
    const controller = new AbortController();
    fetch(`/api/boletin-area/project?id=${encodeURIComponent(project.id)}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error();
      const detail = await response.json();
      if (!controller.signal.aborted) { setLive(detail); onDetail(project.group, detail); }
    }).catch(() => { if (!controller.signal.aborted) setPreviewError(true); });
    return () => controller.abort();
  }, [preview, project.id, project.group, onDetail]);
  const situation = live?.info?.datos.find(dato => dato.bloque === "situacion" && /fase actual|estado actual|situaci[oó]n actual|estado de (?:la|las) obras/i.test(dato.etiqueta));
  const title = project.title;
  const fullSummary = live?.summary || project.summary;
  const excerptEnd = fullSummary.lastIndexOf(". ", 360);
  const summary = fullSummary.length > 400 ? fullSummary.slice(0, excerptEnd > 120 ? excerptEnd + 1 : fullSummary.lastIndexOf(" ", 360)) + "…" : fullSummary;
  return <article className={`area-project-card ${selected ? "is-selected" : ""}`} id={areaProjectElementId(project.group)}>
    <div className="area-project-topline"><button type="button" className="area-project-location" onClick={onSelect} aria-label={`Situar ${project.title} en el mapa`}><span>{String(number).padStart(2, "0")}</span>{project.containsPoint ? "Incluye tu dirección" : `${project.distanceM.toLocaleString("es-ES")} m`}</button><span className={`area-status ${project.recent ? "is-recent" : ""}`}>{project.recent ? "Con novedades en el periodo" : "Sin novedades fechadas en el periodo"}</span></div>
    <p className="area-instrument">{project.instrument}{project.scope === "general" ? " · Alcance amplio" : ""}</p>
    <h3><Link href={project.href}>{title}</Link></h3>
    <p className="area-project-summary">{summary}</p>
    {situation && <div className="area-documented-status"><span>Situación documentada en la ficha</span><p>{situation.valor}</p>{situation.fuenteNombre && <small>{situation.fuenteNombre}{situation.fuenteFecha ? ` · ${situation.fuenteFecha}` : ""}</small>}</div>}
    <div className="area-phase"><span>Última fase documentada</span><strong>{project.phase}</strong>{(project.phaseDate || project.lastMilestone?.date) && <time dateTime={project.phaseDate || project.lastMilestone!.date}>{dateLabel(project.phaseDate || project.lastMilestone!.date)}</time>}</div>
    <p className="area-phase-hint">{areaPhaseHint(project.phase, project.recent)}</p>
    <div className="area-card-actions"><button type="button" aria-expanded={expanded} aria-controls={id} onClick={() => { setExpanded(value => !value); onSelect(); }}>{expanded ? "Cerrar información" : "Ver qué se plantea"}<span aria-hidden="true">{expanded ? "−" : "+"}</span></button><Link href={project.href}>Ficha completa ↗</Link></div>
    {expanded && <div id={id}><AreaProjectExpansion id={project.id} href={project.href} prefetched={live} pending={preview && !live && !previewError} /></div>}
  </article>;
}

function LicenseRow({ event }: { event: BoletinEvento }) {
  const date = areaDate(event.fecha);
  return <li className="area-license-row"><div><LicenciaTitulo tipoExpediente={event.titulo} className="font-medium text-[var(--portal-ink)]" notaClassName="mt-1 text-xs text-slate-500" /><p>{event.direccion || event.detalle || "Dirección no disponible"}</p></div><div className="area-license-meta"><span>{event.distanciaM != null ? `${event.distanciaM} m` : "En el entorno"}</span><time dateTime={date || undefined}>{date ? dateLabel(date) : "Sin fecha precisa"}</time></div></li>;
}

export function AreaExperience({ data }: { data: BoletinAreaResult }) {
  const id = useId();
  const [tab, setTab] = useState<Tab>("resumen");
  const [filter, setFilter] = useState("todos");
  const [visibleProjects, setVisibleProjects] = useState(8);
  const [visibleLicenses, setVisibleLicenses] = useState(12);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [showProjects, setShowProjects] = useState(true);
  const [showLicenses, setShowLicenses] = useState(true);
  const [retry, setRetry] = useState(0);
  const [response, setResponse] = useState<{ key: string; context?: AreaContext; error?: string }>({ key: "" });
  const key = `${data.center.lat}:${data.center.lng}:${data.params.radiusM}:${data.params.months}`;
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ lat: String(data.center.lat), lng: String(data.center.lng), radiusM: String(data.params.radiusM), months: String(data.params.months) });
    fetch(`/api/boletin-area/context?${params}`, { signal: controller.signal }).then(async result => {
      const body = await result.json();
      if (!result.ok) throw new Error(body.error || "No se pudo cargar el contexto urbanístico");
      if (!controller.signal.aborted) setResponse({ key, context: body });
    }).catch(error => { if (!controller.signal.aborted) setResponse({ key, error: error.message }); });
    return () => controller.abort();
  }, [key, retry, data.center.lat, data.center.lng, data.params.radiusM, data.params.months]);
  const context = response.key === key ? response.context : undefined;
  const contextError = response.key === key ? response.error : undefined;
  const hasContext = Boolean(context);
  const asOf = context?.asOf || areaToday(), cutoff = context?.cutoff || areaCutoff(asOf, data.params.months);
  const [liveDetails, setLiveDetails] = useState<Record<string, AreaProjectDetail>>({});
  const acceptDetail = useCallback((group: string, detail: AreaProjectDetail) => setLiveDetails(previous => ({ ...previous, [group]: detail })), []);
  useEffect(() => {
    if (!context) return;
    const controller = new AbortController();
    for (const project of context.projects.filter(project => project.scope === "general").slice(0, 2)) {
      fetch(`/api/boletin-area/project?id=${encodeURIComponent(project.id)}`, { signal: controller.signal }).then(async response => {
        if (!response.ok) return;
        const detail = await response.json();
        if (!controller.signal.aborted) acceptDetail(project.group, detail);
      }).catch(() => {});
    }
    return () => controller.abort();
  }, [context, acceptDetail]);
  const projects = useMemo(() => (context?.projects || []).map(project => liveDetails[project.group] ? enrichAreaProject(project, liveDetails[project.group], asOf, cutoff) : project), [context, liveDetails, asOf, cutoff]);

  const [monthly, setMonthly] = useState<{ key: string; data?: MonthlyLicenseSummary; error?: boolean }>({ key: "" });
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ lat: String(data.center.lat), lng: String(data.center.lng), radiusM: String(data.params.radiusM), months: String(data.params.months) });
    fetch(`/api/boletin-area/monthly?${params}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error();
      const summary = await response.json();
      if (!controller.signal.aborted) setMonthly({ key, data: summary });
    }).catch(() => { if (!controller.signal.aborted) setMonthly({ key, error: true }); });
    return () => controller.abort();
  }, [key, data.center.lat, data.center.lng, data.params.radiusM, data.params.months]);
  const monthlyData = monthly.key === key ? monthly.data : undefined;
  const licensePeriodLabel = monthlyData ? monthlyData.periodMonths === 1 ? "Último mes" : monthlyData.periodMonths === 12 ? "Último año" : `Últimos ${monthlyData.periodMonths} meses` : "";
  const approvals = projects.flatMap(project => project.milestones.filter(event => /aprobaci[oó]n|aprobado/i.test(event.label) && !/publicaci[oó]n/i.test(event.label) && event.date >= cutoff && event.date <= asOf).map(event => ({ project, event }))).sort((a, b) => b.event.date.localeCompare(a.event.date));
  const latestApproval = approvals[0];
  const newsTitle = (project: AreaProject) => /uso terciario de hospedaje|uso hotelero/i.test(project.summary) && !/hotel|hospedaje/i.test(project.title) ? `Uso hotelero en ${project.title}` : project.title;
  const latestProject = [...projects].filter(project => project.lastMilestone && project.lastMilestone.date >= cutoff && project.lastMilestone.date <= asOf && project.group !== latestApproval?.project.group).sort((a, b) => b.lastMilestone!.date.localeCompare(a.lastMilestone!.date))[0];

  const framework = projects.filter(project => project.scope === "general" || (!project.recent && /definitiva|aprobado/i.test(project.phase)));
  const localProjects = projects.filter(project => project.scope !== "general");
  const licenses = useMemo(() => [...new Map([...data.timeline.filter(event => event.tipo === "licencia"), ...data.licencias].map(event => [`${event.ndp}:${event.titulo}:${event.fecha}:${event.detalle}`, event])).values()].sort((a, b) => (areaDate(b.fecha) || "").localeCompare(areaDate(a.fecha) || "")), [data]);
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of licenses) { const title = licenciaTituloDesdeTipo(event.titulo); counts.set(title, (counts.get(title) || 0) + 1); }
    return [...counts].sort((a, b) => b[1] - a[1]).slice(0, 4);
  }, [licenses]);
  const changes = [
    ...projects.flatMap(project => project.milestones.filter(event => event.date >= cutoff && event.date <= asOf).map(event => ({ key: `${project.group}:${event.date}:${event.label}`, date: event.date, title: event.label, description: project.title, href: project.href, kind: "Tramitación", project }))),
    ...licenses.flatMap((event, index) => { const date = areaDate(event.fecha); return date && date >= cutoff && date <= asOf ? [{ key: `license:${index}`, date, title: licenciaTituloDesdeTipo(event.titulo), description: event.direccion || event.detalle, href: null, kind: "Licencia", project: null }] : []; }),
  ].sort((a, b) => b.date.localeCompare(a.date) || Number(Boolean(b.project)) - Number(Boolean(a.project)));
  const last90 = new Date(`${asOf}T12:00:00Z`); last90.setUTCDate(last90.getUTCDate() - 90);
  const recentChanges = changes.filter(change => change.date >= last90.toISOString().slice(0, 10));
  const visibleChanges = tab === "resumen" ? changes.slice(0, 5) : changes;
  const filteredProjects = projects.filter(project => filter === "todos" || (filter === "movimientos" ? project.recent : project.containsPoint));
  const mapEvents: BoletinEvento[] = projects.filter(project => project.scope !== "general" && !hasBroadMapExtent(project.geometry)).map(project => ({ tipo: "sigma", fecha: project.lastMilestone?.date || null, titulo: project.title, detalle: project.phase, expedienteGrupo: project.group, lat: project.location[1], lng: project.location[0] }));
  const selectProject = (project: AreaProject) => { setSelectedGroup(project.group); setShowProjects(true); };
  const locateProject = (group: string) => {
    setSelectedGroup(group); setTab("proyectos"); setFilter("todos"); setVisibleProjects(projects.length);
    requestAnimationFrame(() => document.getElementById(areaProjectElementId(group))?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
  };
  const tabs: { value: Tab; label: string; count?: string }[] = [
    { value: "resumen", label: "Visión de conjunto" },
    { value: "proyectos", label: "Proyectos y planes", count: hasContext ? String(context!.total) : undefined },
    { value: "cambios", label: "Qué ha cambiado", count: String(changes.length) },
    { value: "licencias", label: "Licencias", count: boletinStatLabel(data.stats.licencias, data.stats.licenciasCapped) },
  ];

  const projectGrid = (items: AreaProject[]) => <div className="area-project-grid">{items.map(project => <ProjectCard key={project.group} project={project} number={projects.indexOf(project) + 1} selected={selectedGroup === project.group} preview={tab === "resumen"} onDetail={acceptDetail} onSelect={() => selectProject(project)} />)}</div>;
  const contextStatus = !hasContext ? <div className="area-context-status" role="status">{contextError ? <><p>{contextError}</p><button type="button" onClick={() => { setResponse({ key: "" }); setRetry(value => value + 1); }}>Reintentar proyectos</button></> : <><div className="area-skeleton" /><p>Localizando proyectos y leyendo el contexto urbanístico…</p></>}</div> : null;
  const changesSection = <section className="area-section" aria-labelledby={`${id}-changes`}>
    <header className="area-section-heading"><div><p className="area-eyebrow">Movimientos documentados</p><h3 id={`${id}-changes`}>Qué ha cambiado</h3></div>{tab === "resumen" && <button type="button" className="area-text-link" onClick={() => setTab("cambios")}>Ver la secuencia completa ↗</button>}</header>
    <p className="area-section-intro">{recentChanges.length ? `${recentChanges.length} registros de la muestra en los últimos 90 días.` : "No hay hitos con fecha en los últimos 90 días en los registros consultados."} {changes.length ? `El último es del ${dateLabel(changes[0].date)}.` : ""}</p>
    {!changes.length ? <div className="area-empty">No hay movimientos fechados en el periodo consultado. Los planes anteriores siguen disponibles en «Proyectos y planes».</div> : <ol className="area-changes">{visibleChanges.map(change => <li key={change.key}><time dateTime={change.date}>{dateLabel(change.date)}</time><div><span className={`area-change-kind ${change.project ? "is-project" : ""}`}>{change.kind}</span><h4>{change.title}</h4><p>{change.description}</p>{change.href && <Link href={change.href}>Abrir ficha del proyecto ↗</Link>}</div></li>)}</ol>}
    <p className="area-detail-note">Fechas de trámites y registros, no de inicio o fin de obra. La secuencia de licencias muestra los registros recuperados, no un censo exhaustivo.</p>
  </section>;

  return <section className="area-experience" aria-label="Información del entorno">
    <header className="area-place-heading"><div><p className="area-eyebrow">Una lectura de tu entorno · {data.params.radiusM.toLocaleString("es-ES")} m a la redonda</p><h1>{data.center.direccion || "El entorno de tu dirección"}</h1><p>{[data.center.distrito, data.center.barrio].filter(Boolean).join(" · ") || "Madrid capital"} <span>·</span> Movimientos de los últimos {data.params.months} meses</p></div></header>
    {(latestApproval || latestProject || Boolean(monthlyData?.categories.length)) && <div className="area-news-summary" aria-label="Lo que importa en tu zona">
      {latestApproval && <Link className="area-news-card" href={latestApproval.project.href}>
        <span className="area-news-label">Última aprobación</span><strong className="area-news-title">{newsTitle(latestApproval.project)}</strong><span className="area-news-meta">{latestApproval.event.label} · {dateLabel(latestApproval.event.date)}</span>
      </Link>}
      {latestProject && <Link className="area-news-card" href={latestProject.href}>
        <span className="area-news-label">Proyecto con novedades</span><strong className="area-news-title">{newsTitle(latestProject)}</strong><span className="area-news-meta">{latestProject.lastMilestone!.label} · {dateLabel(latestProject.lastMilestone!.date)}</span>
      </Link>}
      {monthlyData?.categories.filter(category => category.count > 0).map(category => <button type="button" key={category.label} className="area-news-card area-news-license" onClick={() => setTab("licencias")}>
        <strong className="area-news-number">{category.count.toLocaleString("es-ES")}</strong><span className="area-news-label">{category.label}</span><span className="area-news-meta" title={`${dateLabel(monthlyData.from)} – ${dateLabel(monthlyData.to)}`}>{licensePeriodLabel}</span>
      </button>)}
    </div>}
    {!hasContext && !contextError && <p className="area-summary-note" role="status">Consultando las novedades de la zona…</p>}
    {monthlyData && <p className="area-summary-note">Licencias: {licensePeriodLabel.toLowerCase()} · {dateLabel(monthlyData.from)} – {dateLabel(monthlyData.to)}.{monthlyData.expanded ? " Periodo ampliado automáticamente dentro del filtro de la búsqueda." : ""} Por fecha de concesión, incluidas las declaraciones responsables según su tipo de actuación.{monthlyData.latestDate && monthlyData.latestDate < areaCutoff(monthlyData.to,1) ? ` El archivo disponible tiene registros hasta el ${dateLabel(monthlyData.latestDate)}.` : ""}</p>}
    {monthly.key === key && monthly.error && <p className="area-summary-note" role="status">El resumen mensual de licencias no está disponible ahora.</p>}
    <div className="area-reading-note"><span aria-hidden="true">↳</span><p>{hasContext ? (context!.containsCount ?? projects.filter(project => project.containsPoint).length) ? `${context!.containsCount ?? projects.filter(project => project.containsPoint).length} ámbitos de planeamiento incluyen tu dirección. ` : "Los proyectos se localizan por la distancia a su ámbito, no a su centro. " : "Estamos completando la lectura de proyectos y planeamiento. "}Las licencias muestran actividad administrativa; la ejecución de una obra se comprueba en la ficha y sus fuentes.</p></div>
    {context?.snapshot && <p className="area-inline-notice">No se pudo actualizar la cartografía municipal. Se muestra el catálogo disponible; consulta las fichas para revisar su estado.</p>}
    {context?.limited && <p className="area-inline-notice">Se muestran {projects.length} de {context.total} expedientes localizados. Reduce el radio para una lectura más concreta.</p>}
    <div className="area-tabs" role="tablist" aria-label="Explorar tu zona" onKeyDown={event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const current = tabs.findIndex(item => item.value === tab);
      const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      setTab(tabs[next].value);
      requestAnimationFrame(() => document.getElementById(`${id}-${tabs[next].value}-tab`)?.focus());
    }}>{tabs.map(item => <button key={item.value} id={`${id}-${item.value}-tab`} type="button" role="tab" tabIndex={tab === item.value ? 0 : -1} aria-selected={tab === item.value} aria-controls={`${id}-panel`} onClick={() => setTab(item.value)}>{item.label}{item.count != null && <span>{item.count}</span>}</button>)}</div>
    <div className="area-workspace">
      <div className="area-main" id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${tab}-tab`}>
        {(tab === "resumen" || tab === "proyectos") && <section className="area-section" aria-labelledby={`${id}-projects`}>
          <header className="area-section-heading"><div><p className="area-eyebrow">Actuaciones y expedientes</p><h3 id={`${id}-projects`}>{tab === "resumen" ? "Los proyectos que dan contexto" : "Proyectos y planes de la zona"}</h3></div>{tab === "resumen" && hasContext && <button type="button" className="area-text-link" onClick={() => setTab("proyectos")}>Ver todos ↗</button>}</header>
          <p className="area-section-intro">Qué se plantea, cuál es la última fase conocida y dónde consultar sus documentos. También aparecen planes anteriores al periodo de licencias.</p>
          {contextStatus}
          {tab === "proyectos" && hasContext && <div className="area-filter-chips" aria-label="Filtrar proyectos">{[["todos", "Todos"], ["movimientos", "Con movimientos"], ["incluyen", "Incluyen mi dirección"]].map(([value, label]) => <button type="button" key={value} aria-pressed={filter === value} onClick={() => { setFilter(value); setVisibleProjects(8); }}>{label}</button>)}</div>}
          {hasContext && (tab === "resumen" ? localProjects.length ? projectGrid(localProjects.slice(0, 3)) : <div className="area-empty">{framework.length ? "Los expedientes localizados son de alcance amplio. Puedes consultarlos en el marco urbanístico o en «Proyectos y planes»." : "No se han localizado ámbitos de proyectos en este radio en el catálogo disponible. Puedes ampliar la búsqueda."}</div> : filteredProjects.length ? <>{projectGrid(filteredProjects.slice(0, visibleProjects))}{filteredProjects.length > visibleProjects && <button type="button" className="area-load-more" onClick={() => setVisibleProjects(value => value + 8)}>Ver más expedientes · {filteredProjects.length - visibleProjects} restantes</button>}</> : <div className="area-empty">No hay expedientes que coincidan con este filtro. Prueba «Todos» o amplía el radio.</div>)}
        </section>}
        {tab === "resumen" && framework.length > 0 && <section className="area-framework area-section"><p className="area-eyebrow">El marco urbanístico</p><h3>Planes que ayudan a entender esta zona</h3><p>Planeamiento de alcance amplio y antecedentes aprobados que ayudan a interpretar el entorno. Su vigencia y condiciones se revisan en la documentación.</p><ul>{framework.slice(0, 3).map(project => <li key={project.group}><span>{project.instrument}</span><Link href={project.href}>{project.title} ↗</Link><small>{project.lastMilestone ? `Último hito: ${dateLabel(project.lastMilestone.date)}` : "Sin fecha precisa"} · {distanceLabel(project)}</small></li>)}</ul><button type="button" className="area-text-link" onClick={() => setTab("proyectos")}>Explorar el marco y sus expedientes ↗</button></section>}
        {(tab === "resumen" || tab === "cambios") && changesSection}
        {(tab === "resumen" || tab === "licencias") && <section className="area-section" aria-labelledby={`${id}-licenses`}><header className="area-section-heading"><div><p className="area-eyebrow">La actividad a pie de calle</p><h3 id={`${id}-licenses`}>Licencias en edificios cercanos</h3></div>{tab === "resumen" && <button type="button" className="area-text-link" onClick={() => setTab("licencias")}>Consultar licencias ↗</button>}</header><p className="area-section-intro">Reformas, usos y otras actuaciones registradas. Una licencia no confirma que una obra haya empezado o terminado.</p><div className="area-license-types">{categories.map(([label, count]) => <span key={label}>{label}<b>{count}</b></span>)}</div>{tab === "resumen" ? <p className="area-detail-note">Distribución de los {licenses.length} registros recuperados para esta consulta. Abre «Licencias» para ver direcciones, fechas y expedientes.</p> : <>{licenses.length ? <ul>{licenses.slice(0, visibleLicenses).map((event, index) => <LicenseRow key={`${event.ndp}:${event.fecha}:${index}`} event={event} />)}</ul> : <div className="area-empty">No hay licencias recuperadas con estos filtros.</div>}{licenses.length > visibleLicenses && <button type="button" className="area-load-more" onClick={() => setVisibleLicenses(value => value + 20)}>Mostrar más registros</button>}<p className="area-detail-note">{Math.min(visibleLicenses, licenses.length)} de {licenses.length} registros recuperados. El total registrado es {boletinStatLabel(data.stats.licencias, data.stats.licenciasCapped)}; la consulta devuelve una muestra acotada.</p></>}</section>}
        {tab === "cambios" && contextStatus}
        <footer className="area-sources">Fuentes: registro de licencias y catálogo de planeamiento del Ayuntamiento de Madrid; investigación y documentos enlazados en cada ficha. «Sin novedades fechadas en el periodo» significa que no tenemos movimientos fechados en estos registros, no que el proyecto esté paralizado.</footer>
      </div>
      <aside className="area-map-column" aria-label="Mapa del entorno"><div className="area-map-heading"><div><p className="area-eyebrow">Dónde sucede</p><h3>El mapa de tu zona</h3></div><span>{data.params.radiusM} m</span></div><div className="area-map-controls"><button type="button" aria-pressed={showProjects} onClick={() => setShowProjects(value => !value)}>Proyectos y ámbitos</button><button type="button" aria-pressed={showLicenses} onClick={() => setShowLicenses(value => !value)}>Licencias</button></div><BoletinMiniMap lat={data.center.lat} lng={data.center.lng} radiusM={data.params.radiusM} licencias={showLicenses ? data.licencias : []} expedientesSigma={showProjects ? mapEvents : []} projects={showProjects ? projects.filter(project => project.scope !== "general" && !hasBroadMapExtent(project.geometry)) : []} selectedProject={selectedGroup} onProjectSelect={locateProject} /><p className="area-map-explainer">Los contornos orientativos muestran la parte próxima de los ámbitos; los planes de alcance amplio se consultan en sus fichas, sin dibujarlos en el mapa. Selecciona uno para identificar su expediente. El círculo delimita el radio de la consulta.</p><Link href="/explore" className="area-text-link">Abrir el explorador territorial ↗</Link><LaunchWaitlistSection source="boletin" compact /></aside>
    </div>
  </section>;
}
