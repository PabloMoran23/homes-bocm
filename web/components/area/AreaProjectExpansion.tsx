"use client";

import { useEffect, useState } from "react";
import { ProyectoInfoTabPanel, proyectoInfoTabs } from "@/components/project-detail/ProyectoInfoExtraPanel";
import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import { NtiDocumentList } from "@/components/project-detail/NtiDocumentList";
import { formatM2 } from "@/lib/sigma-metrics";
import type { AreaProjectDetail } from "@/lib/area-context";

export function AreaProjectExpansion({ id, href, prefetched = null, pending = false }: { id: string; href: string; prefetched?: AreaProjectDetail | null; pending?: boolean }) {
  const [state, setState] = useState<{ data: AreaProjectDetail | null; error: string }>({ data: null, error: "" });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (prefetched || pending) return;
    const controller = new AbortController();
    fetch(`/api/boletin-area/project?id=${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(async response => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "No se pudo cargar la ficha");
        if (!controller.signal.aborted) setState({ data: body, error: "" });
      })
      .catch(error => { if (!controller.signal.aborted) setState({ data: null, error: error.message }); });
    return () => controller.abort();
  }, [id, retry, prefetched, pending]);
  if (state.error && !prefetched) return <div className="area-inline-notice" role="status"><p>{state.error}</p><button type="button" onClick={() => { setState({ data: null, error: "" }); setRetry(value => value + 1); }}>Reintentar</button> <a href={href}>Abrir ficha completa ↗</a></div>;
  if (!state.data && !prefetched) return <p className="area-loading" role="status">Cargando la información de la ficha del proyecto…</p>;
  const detail = prefetched || state.data!;
  const tabs = detail.info ? proyectoInfoTabs(detail.info) : [];
  return <div className="area-project-expansion">
    <div className="area-ficha-intro"><span>Información de la ficha del proyecto</span><a href={href}>Abrir ficha completa ↗</a></div>
    <h4 className="area-full-project-title">{detail.title}</h4>
    <dl className="area-project-facts">
      <div><dt>Fase en el catálogo municipal</dt><dd>{detail.phase}</dd></div>
      {detail.group && <div><dt>Referencia del expediente</dt><dd>{detail.group}</dd></div>}
      {detail.metric?.num_viviendas_max != null && <div><dt>Viviendas documentadas</dt><dd>{detail.metric.num_viviendas_max.toLocaleString("es-ES")}</dd></div>}
      {detail.metric?.sup_total_m2 != null && <div><dt>Superficie del ámbito</dt><dd>{formatM2(detail.metric.sup_total_m2)}</dd></div>}
    </dl>
    {detail.info && tabs.length ? tabs.map(tab => <details className="area-ficha-section" key={tab.id} open={tab.id === "relato"}>
      <summary>{tab.label}</summary><ProyectoInfoTabPanel info={detail.info!} tab={tab.id} tramitacion={detail.tramites} />
    </details>) : <p className="area-detail-copy">{detail.summary || "Consulta los datos del registro y la documentación del expediente."}</p>}
    {detail.info?.investigadoAt && <p className="area-detail-note">Investigación revisada el {new Date(detail.info.investigadoAt).toLocaleDateString("es-ES", { timeZone: "Europe/Madrid" })}. Esta fecha no es un hito de obra.</p>}
    {detail.info?.huecos && <p className="area-detail-note">Información pendiente de completar: {detail.info.huecos}</p>}
    {detail.tramites.length > 0 && <details className="area-ficha-section"><summary>Tramitación municipal · {detail.tramites.length} hitos</summary><TramitacionTimeline rows={detail.tramites} compact /></details>}
    {(detail.documents.length > 0 || detail.documentsTotal || detail.documentsUrl) ? <details className="area-ficha-section"><summary>Documentación oficial{detail.documentsTotal ? ` · ${detail.documentsTotal} documentos` : ""}</summary><NtiDocumentList linked={null} muestra={detail.documents} totalVisor={detail.documentsTotal} listadoUrl={detail.documentsUrl} /></details> : null}
    {detail.sourceUrl && <a className="area-text-link" href={detail.sourceUrl} target="_blank" rel="noreferrer">Consultar la fuente original ↗</a>}
  </div>;
}
