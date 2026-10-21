"use client";

import { useId, useState } from "react";
import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import {
  PROYECTO_INFO_BLOQUE_LABEL,
  type ProyectoInfoBloque,
  type ProyectoInfoDato,
  type ProyectoInfoExtra,
  type ProyectoInfoHallazgo,
} from "@/lib/proyecto-info-extra";
import type { SigmaVisorTramite } from "@/lib/types";
import { proyectoHitoFecha } from "@/lib/proyecto-timeline";

const CONFIANZA_LABEL = { alta: "Alta", media: "Media", baja: "Baja" } as const;
const FUENTE_LABEL = { oficial: "Oficial", prensa: "Prensa", web: "Web" } as const;

const DATOS_COLUMNAS: ProyectoInfoBloque[][] = [
  ["situacion", "programa"],
  ["cifras", "actores"],
];

function StoryDisclosure({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();
  return <div className="research-story-more">
    <div id={contentId} hidden={!expanded}>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{text}</p>
    </div>
    <button type="button" className="research-read-toggle" aria-expanded={expanded} aria-controls={contentId}
      onClick={event => {
        const button = event.currentTarget;
        setExpanded(!expanded);
        if (expanded) requestAnimationFrame(() => button.scrollIntoView({ block: "nearest", behavior: "instant" }));
      }}>{expanded ? "Ver menos" : "Ver más"}</button>
  </div>;
}

export type ProyectoInfoTabId = "relato" | "datos" | "cronologia" | "prensa";

function formatDay(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" });
}

export function proyectoInfoTabs(info: ProyectoInfoExtra): { id: ProyectoInfoTabId; label: string }[] {
  const tabs: { id: ProyectoInfoTabId; label: string }[] = [];
  if (info.resumen.trim()) tabs.push({ id: "relato", label: "Qué está pasando" });
  if (info.datos.some((dato) => DATOS_COLUMNAS.flat().includes(dato.bloque) && dato.clave !== "nombre_publico")) {
    tabs.push({ id: "datos", label: "Datos" });
  }
  if (info.datos.some((dato) => dato.bloque === "cronologia")) {
    tabs.push({ id: "cronologia", label: "Cronología" });
  }
  if (info.datos.some((dato) => dato.bloque === "prensa") || info.hallazgos.length > 0) {
    tabs.push({ id: "prensa", label: "Prensa" });
  }
  return tabs;
}

export function proyectoNombrePopular(info: ProyectoInfoExtra): string | null {
  const row = info.datos.find((dato) => dato.clave === "nombre_publico" && dato.valor.trim());
  return row?.valor.trim() ?? null;
}

function formatChipValue(dato: ProyectoInfoDato): { label: string; value: string } | null {
  if (dato.clave === "num_viviendas" && dato.valorNumero != null) {
    return { label: "Viviendas", value: Math.round(dato.valorNumero).toLocaleString("es-ES") };
  }
  if (dato.clave === "sup_total_m2" && dato.valorNumero != null) {
    const n = dato.valorNumero;
    const value =
      n >= 1_000_000
        ? `${(n / 1_000_000).toLocaleString("es-ES", { maximumFractionDigits: 1 })} km²`
        : `${Math.round(n).toLocaleString("es-ES")} m²`;
    return { label: "Superficie", value };
  }
  if (dato.clave === "promotor") {
    const raw = dato.valor.split(/[,(—-]/)[0]?.trim() || dato.valor;
    return { label: "Impulsa", value: raw.length > 36 ? `${raw.slice(0, 34)}…` : raw };
  }
  return null;
}

export function proyectoInfoChips(info: ProyectoInfoExtra): { label: string; value: string; key: string }[] {
  const order = ["num_viviendas", "sup_total_m2", "promotor"];
  const out: { label: string; value: string; key: string }[] = [];
  for (const clave of order) {
    const dato = info.datos.find((row) => row.clave === clave && row.destacado) ?? info.datos.find((row) => row.clave === clave);
    if (!dato) continue;
    const chip = formatChipValue(dato);
    if (chip) out.push({ ...chip, key: clave });
  }
  return out;
}

function FuenteDisclosure({ dato }: { dato: ProyectoInfoDato }) {
  const parts = [
    FUENTE_LABEL[dato.fuenteTipo],
    dato.fuenteNombre,
    formatDay(dato.fuenteFecha),
    CONFIANZA_LABEL[dato.confianza],
  ].filter(Boolean);
  if (!parts.length && !dato.extracto && !dato.fuenteUrl) return null;
  const text = parts.join(" · ");
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">Fuente</summary>
      {dato.extracto ? <p className="mt-1 text-sm italic text-slate-600">“{dato.extracto}”</p> : null}
      <p className="mt-1 text-xs text-slate-500">
        {dato.fuenteUrl ? (
          <a
            href={dato.fuenteUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-slate-300 underline-offset-2 hover:text-slate-700"
          >
            {text || "Abrir fuente"}
          </a>
        ) : (
          text
        )}
      </p>
    </details>
  );
}

function DatoRow({ dato }: { dato: ProyectoInfoDato }) {
  return (
    <div className={`research-datum border-b border-slate-100 py-3 last:border-0 ${dato.valorNumero != null ? "research-datum-numeric" : ""}`}>
      <p className="text-xs font-medium text-slate-500">{dato.etiqueta}</p>
      <p className="mt-1 text-sm leading-relaxed text-slate-900">{dato.valor}</p>
      <FuenteDisclosure dato={dato} />
    </div>
  );
}

function SectionIcon({ bloque }: { bloque: ProyectoInfoBloque }) {
  const paths: Record<ProyectoInfoBloque, React.ReactNode> = {
    situacion: <><path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
    programa: <><path d="M4 21V7l8-4 8 4v14M2 21h20M9 21v-5h6v5M8 9h1m6 0h1M8 12h1m6 0h1" /></>,
    cifras: <><path d="m3 16 13-13 5 5L8 21Zm7-7 3 3m0-6 3 3m-9 3 3 3" /></>,
    actores: <><circle cx="9" cy="7" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v3" /></>,
    cronologia: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    prensa: <><path d="M5 4h15v16H5a2 2 0 0 1-2-2V8h2Zm0 0v14M8 8h8M8 12h8m-8 4h4" /></>,
  };
  return <svg className="research-section-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[bloque]}</svg>;
}

function BloqueList({ info, bloque }: { info: ProyectoInfoExtra; bloque: ProyectoInfoBloque }) {
  const rows = info.datos.filter((dato) => dato.bloque === bloque && dato.clave !== "nombre_publico");
  if (!rows.length) return null;
  return (
    <section className="research-data-block">
      <header className="research-data-heading"><SectionIcon bloque={bloque} /><h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {bloque === "programa" && info.tipoEntrada && info.tipoEntrada !== "actuacion" ? "Contenido y condiciones" : PROYECTO_INFO_BLOQUE_LABEL[bloque]}
      </h3><span>{rows.length} {rows.length === 1 ? "dato" : "datos"}</span></header>
      <div className="mt-1">
        {rows.map((dato) => (
          <DatoRow key={`${dato.orden}-${dato.etiqueta}`} dato={dato} />
        ))}
      </div>
    </section>
  );
}

function HallazgoItem({ hallazgo }: { hallazgo: ProyectoInfoHallazgo }) {
  return (
    <li className="research-news-card research-note-card">
      <p className="research-news-type">Análisis y contexto</p>
      <p className="text-sm font-semibold text-slate-900">{hallazgo.titulo}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{hallazgo.cuerpo}</p>
      {hallazgo.fuenteNombre || hallazgo.fuenteUrl ? (
        <p className="mt-1 text-xs text-slate-500">
          {hallazgo.fuenteUrl ? (
            <a
              href={hallazgo.fuenteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-slate-300 underline-offset-2 hover:text-slate-700"
            >
              {hallazgo.fuenteNombre || "Fuente"}
              {formatDay(hallazgo.fuenteFecha) ? ` · ${formatDay(hallazgo.fuenteFecha)}` : ""}
            </a>
          ) : (
            <>
              {hallazgo.fuenteNombre}
              {formatDay(hallazgo.fuenteFecha) ? ` · ${formatDay(hallazgo.fuenteFecha)}` : ""}
            </>
          )}
        </p>
      ) : null}
    </li>
  );
}

export function ProyectoInfoLead({
  info,
  stacked = false,
}: {
  info: ProyectoInfoExtra;
  stacked?: boolean;
}) {
  const destacados = proyectoInfoChips(info);
  if (!destacados.length) return null;
  return (
    <div className={stacked ? "grid h-full grid-rows-3 gap-2" : "mb-4 grid gap-2 sm:grid-cols-3"}>
      {destacados.map((dato) => (
        <div
          key={dato.key}
          className="flex flex-col justify-center rounded-xl bg-white px-3 py-2.5 ring-1 ring-slate-200"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{dato.label}</p>
          <p className="mt-0.5 text-base font-bold leading-snug text-slate-900">{dato.value}</p>
        </div>
      ))}
    </div>
  );
}

export function ProyectoInfoTabPanel({
  info,
  tab,
  tramitacion,
}: {
  info: ProyectoInfoExtra;
  tab: ProyectoInfoTabId;
  tramitacion?: SigmaVisorTramite[] | null;
}) {
  if (!proyectoInfoTabs(info).some((item) => item.id === tab)) return null;

  if (tab === "relato") {
    const resumen = info.resumen.trim();
    const paragraphEnd = resumen.indexOf("\n\n");
    const sentenceEnd = resumen.indexOf(". ", 200);
    const splitAt = resumen.length > 600
      ? paragraphEnd > 0 && paragraphEnd <= 500 ? paragraphEnd
        : sentenceEnd >= 0 && sentenceEnd <= 500 ? sentenceEnd + 1
          : resumen.lastIndexOf(" ", 420)
      : -1;
    const intro = splitAt > 0 ? resumen.slice(0, splitAt) : resumen;
    const rest = splitAt > 0 ? resumen.slice(splitAt).trim() : "";
    return (
      <div className="research-story">
        <h2 className="text-lg font-semibold text-slate-900">Qué está pasando</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{intro}</p>
        {rest ? <StoryDisclosure text={rest} /> : null}
      </div>
    );
  }

  if (tab === "datos") {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-slate-900">Datos</h2>
        <div className="research-data-sections space-y-8">
          {(["situacion", "programa", "cifras", "actores"] as const).map((bloque) => (
            <BloqueList key={bloque} info={info} bloque={bloque} />
          ))}
        </div>
      </div>
    );
  }

  if (tab === "cronologia") {
    const rows = info.datos.filter((dato) => dato.bloque === "cronologia");
    const events = rows.map(dato => ({ dato, fecha: proyectoHitoFecha(dato) }))
      .sort((a, b) => (a.fecha.year ?? Infinity) - (b.fecha.year ?? Infinity) || a.dato.orden - b.dato.orden);
    const years = Array.from(new Set(events.map(event => event.fecha.year)));
    return (
      <div className="space-y-8">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Cronología</h2>
          <p className="research-timeline-intro">Hitos documentados del proyecto · Secuencia por año</p>
          <ol className="research-timeline" aria-label="Hitos relevantes en orden cronológico">
            {years.map(year => <li className="research-timeline-year" key={year ?? "undated"}>
              <div className="research-timeline-marker"><span aria-hidden="true" /><strong>{year ?? "Sin fecha"}</strong></div>
              <div className="research-timeline-events">{events.filter(event => event.fecha.year === year).map(({ dato, fecha }) => <article className="research-event" key={`${dato.orden}-${dato.etiqueta}`}>
                <p className="research-event-date">{fecha.label}</p><h3>{dato.etiqueta}</h3><p className="research-event-description">{dato.valor}</p><FuenteDisclosure dato={dato} />
              </article>)}</div>
            </li>)}
          </ol>
        </div>
        {tramitacion && tramitacion.length > 0 ? (
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Tramitación del ayuntamiento</h3>
            <div className="mt-4">
              <TramitacionTimeline rows={tramitacion} />
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  const prensa = info.datos.filter((dato) => dato.bloque === "prensa");
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Prensa</h2>
        {prensa.length > 0 ? (
          <div className="research-press-grid mt-6">
            {prensa.map((dato) => (
              <article className="research-news-card" key={`${dato.orden}-${dato.etiqueta}`}>
                <div className="research-news-meta"><SectionIcon bloque="prensa" /><span>{dato.fuenteNombre || FUENTE_LABEL[dato.fuenteTipo]}</span></div>
                {formatDay(dato.fuenteFecha) ? <p className="research-news-date">{formatDay(dato.fuenteFecha)}</p> : null}
                <h3>{dato.etiqueta}</h3><p className="research-news-body">{dato.valor}</p>
                <FuenteDisclosure dato={dato} />
                {dato.fuenteUrl ? <a className="research-news-link" href={dato.fuenteUrl} target="_blank" rel="noopener noreferrer">Leer publicación <span aria-hidden="true">↗</span></a> : null}
              </article>
            ))}
          </div>
        ) : null}
      </div>
      {info.hallazgos.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Otras notas</h3>
          <ul className="research-notes-grid mt-4">
            {info.hallazgos.map((hallazgo) => (
              <HallazgoItem key={`${hallazgo.orden}-${hallazgo.titulo}`} hallazgo={hallazgo} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
