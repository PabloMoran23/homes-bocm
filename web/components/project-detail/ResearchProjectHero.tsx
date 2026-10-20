import type { ReactNode } from "react";
import { proyectoInfoChips } from "./ProyectoInfoExtraPanel";
import type { ProyectoInfoExtra } from "@/lib/proyecto-info-extra";

export function ResearchProjectHero({ title, location, subtitle, info, map, actions }: {
  title: string;
  location: string;
  subtitle?: string | null;
  info: ProyectoInfoExtra;
  map: ReactNode;
  actions?: ReactNode;
}) {
  const metrics = proyectoInfoChips(info);
  const [displayTitle, designation] = title.split(/\s[—–]\s/);
  const date = info.investigadoAt ? new Date(info.investigadoAt) : null;
  const updated = date && !Number.isNaN(date.getTime())
    ? date.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Madrid" })
    : null;
  return (
    <header className="research-hero">
      <div className="research-hero-heading">
        <div>
          <p className="research-eyebrow">Explorador territorial <span>/</span> {location}</p>
          <h1>{displayTitle}</h1>
          {designation || subtitle ? <p className="research-subtitle">{designation || subtitle}</p> : null}
        </div>
        <a className="research-outline-link" href="#investigacion">Explorar investigación <span aria-hidden="true">↓</span></a>
      </div>
      <div className="research-territory">
        <div className="research-map">
          {map}
          <div className="research-map-caption"><span className="research-map-key" aria-hidden="true" /> Ámbito del proyecto <span>Cartografía interactiva</span></div>
        </div>
        <aside className="research-overview" aria-label="Resumen del proyecto">
          <p className="research-eyebrow">El proyecto en un vistazo</p>
          <h2>Territorio y contexto</h2>
          {info.resumen.trim() ? <p className="research-summary">{info.resumen}</p> : <p className="research-summary">Consulta los datos documentados y las fuentes de este proyecto en las secciones siguientes.</p>}
          {info.resumen.trim() ? <a className="research-read-more" href="#seccion-relato">Leer resumen completo <span aria-hidden="true">↗</span></a> : null}
          {metrics.length ? <dl className="research-metrics">{metrics.map(metric => <div key={metric.key}><dt>{metric.label}</dt><dd>{metric.value}</dd></div>)}</dl> : null}
          {actions ? <div className="research-source-actions">{actions}</div> : null}
          {updated ? <p className="research-updated">Investigación actualizada el {updated}</p> : null}
        </aside>
      </div>
    </header>
  );
}
