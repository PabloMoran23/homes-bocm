"use client";

import Link from "next/link";
import { useEffect, useId } from "react";
import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";
import type { MapProjectSpotlightItem } from "@/lib/map-project-spotlight";

export function MapProjectDetailCard({ item, visible, onClose }: {
  item: MapProjectSpotlightItem | null;
  visible: boolean;
  onClose?: () => void;
}) {
  const titleId = useId();
  useEffect(() => {
    if (!visible || !item || !onClose) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [visible, item, onClose]);
  if (!visible || !item) return null;

  const metrics = [
    item.supM2 != null ? { label: "Superficie", value: `${item.supM2.toLocaleString("es-ES")} m²` } : null,
    item.numViviendas != null ? { label: "Viviendas", value: item.numViviendas.toLocaleString("es-ES") } : null,
    item.dateLabel ? { label: item.dateMetricLabel || "Última actividad", value: item.dateLabel } : null,
    ...(item.extraMetrics ?? []),
  ].filter((metric): metric is { label: string; value: string } => metric != null);

  return (
    <aside aria-labelledby={titleId} className="map-project-detail-card pointer-events-auto absolute inset-x-3 bottom-3 z-[2200] flex max-h-[calc(100%-4.5rem)] flex-col overflow-hidden rounded-2xl border border-white/80 bg-white shadow-[0_12px_48px_rgba(42,38,34,0.20)] lg:inset-x-auto lg:bottom-5 lg:right-5 lg:w-[390px]">
      <article className="min-h-0 max-h-[min(65dvh,560px)] overflow-y-auto overscroll-contain">
        <div className="relative overflow-hidden bg-gradient-to-br from-[#dce8dd] via-[#e8efe8] to-[#f7f3eb] px-5 pb-4 pt-4">
          <svg viewBox="0 0 390 150" className="pointer-events-none absolute inset-0 h-full w-full opacity-25" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <path d="M-30 120 125 34 220 104 410 20M-20 50 94 110 235 -10M170 170 260 90 430 115" fill="none" stroke="#4a7578" strokeWidth="2" />
            <path d="m290 10 55 22-18 48-59-18zm-110 55 54 10-10 37-65-20zM55 15l56 16-9 40-58-14z" fill="#9eb89e" stroke="#6b8f54" />
          </svg>
          <div className="relative flex items-start justify-between gap-3">
            <span className="max-w-[calc(100%-3.5rem)] rounded-full bg-white/90 px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-[#1f4f53]">{item.fase || item.categoryLabel}</span>
            {onClose ? <button type="button" onClick={onClose} aria-label={item.tag === "Licencia" ? "Cerrar licencia" : "Cerrar proyecto"} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/90 text-slate-600 transition hover:bg-white hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#1f4f53]"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg></button> : null}
          </div>
          <div className="relative mt-5 flex items-end gap-3">
            {item.badgeIcon ? <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md" style={{ backgroundColor: item.badgeIcon.bg }} aria-hidden="true" dangerouslySetInnerHTML={{ __html: item.badgeIcon.svg }} /> : <SigmaClassificationIcon clasificacion={{ categoriaProyecto: item.categoriaProyecto, tipoObra: item.tipoObra }} size="sm" />}
            <div className="min-w-0 flex-1">
              {item.expedienteGrupo ? <p className="mb-1 truncate text-[10px] font-medium tracking-wide text-[#516663]">{item.expedienteGrupo}</p> : null}
              <h3 id={titleId} className="break-words text-[17px] font-bold leading-tight tracking-tight text-[#253c38]">{item.title}</h3>
            </div>
          </div>
        </div>
        <div className="space-y-3 px-5 pb-5 pt-4">
          {item.locationLine ? <p className="text-xs font-medium text-slate-500">{item.locationLine}</p> : null}
          {item.approx ? <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">Ubicación aproximada. El marcador se distribuye cerca del centro del municipio y no señala la parcela del proyecto.</p> : null}
          {item.resumen ? <p className="line-clamp-4 text-[13px] leading-relaxed text-slate-600">{item.resumen}</p> : null}
          {metrics.length ? <dl className={`grid gap-2 ${metrics.length === 3 ? "grid-cols-2 min-[380px]:grid-cols-3" : metrics.length === 2 ? "grid-cols-2" : "grid-cols-1"}`}>{metrics.map(metric => <div key={metric.label} className="min-w-0 break-words rounded-xl bg-[#f1f5f3] px-2.5 py-3"><dt className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-slate-500">{metric.label}</dt><dd className="text-xs font-bold leading-snug text-slate-800">{metric.value}</dd></div>)}</dl> : null}
          {item.fase ? <div className="flex items-center gap-2 rounded-xl border border-[#dce8dd] bg-[#f5f8f5] px-3 py-2.5"><span className="h-2 w-2 shrink-0 rounded-full bg-[#4a7578]" aria-hidden="true" /><p className="text-xs font-medium text-[#365b55]">{item.fase}</p></div> : null}
          <Link href={item.href} className="flex min-h-10 items-center justify-center gap-2 rounded-lg bg-[#1f4f53] px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-[#16383b] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#1f4f53]"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M4 2h5l3 3v9H4V2Z" stroke="currentColor" strokeWidth="1.2" /><path d="M9 2v3h3M6 8h4M6 10h4" stroke="currentColor" strokeWidth="1.2" /></svg>Ver ficha completa</Link>
        </div>
      </article>
    </aside>
  );
}
