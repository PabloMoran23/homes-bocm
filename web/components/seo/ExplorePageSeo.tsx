import Link from "next/link";
import { SeoFaq } from "@/components/seo/SeoFaq";

const EXPLORE_FAQ = [
  {
    q: "¿Qué puedo ver en el mapa?",
    a: "Obras con licencia, planes urbanísticos en tramitación y proyectos que pueden cambiar tu barrio: nuevos edificios, reformas de uso, reparcelaciones y actuaciones sobre el suelo. Todo geolocalizado en Madrid capital.",
  },
  {
    q: "¿Qué diferencia hay entre una licencia y un plan?",
    a: "La licencia autoriza una obra concreta en un edificio o parcela. El planeamiento define las reglas de una zona más amplia — por ejemplo un plan especial o un estudio de detalle — antes de que se construya.",
  },
  {
    q: "¿Cómo busco una calle o un proyecto?",
    a: "Abre el panel de filtros y escribe en el buscador. También puedes introducir tu dirección en el boletín de tu zona si quieres ver qué ha pasado cerca de casa. Cada proyecto tiene su ficha con trámites y documentos.",
  },
  {
    q: "¿Con qué frecuencia se actualizan los datos?",
    a: "Semanalmente, a partir de fuentes públicas del Ayuntamiento de Madrid. La fecha de la última actualización aparece en la portada y en las estadísticas.",
  },
] as const;

/** Panel colapsado sobre el mapa: no ocupa altura del viewport. El H1 vive aquí para SEO. */
export function ExplorePageSeoPanel() {
  return (
    <details className="group absolute bottom-3 left-3 z-[1080] max-w-[min(calc(100%-5.5rem),16rem)] rounded-xl border border-slate-200/90 bg-white/95 shadow-lg backdrop-blur-sm sm:bottom-4 sm:left-auto sm:right-4 sm:max-w-sm">
      <summary className="cursor-pointer list-none rounded-xl px-3 py-2 text-xs font-medium text-slate-700 marker:content-none sm:px-4 sm:py-2.5 sm:text-sm [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-2">
          <span
            className="text-[10px] text-slate-400 transition group-open:rotate-90"
            aria-hidden
          >
            ▶
          </span>
          Licencias y planes en Madrid
        </span>
      </summary>
      <div className="max-h-[min(50dvh,18rem)] overflow-y-auto border-t border-slate-100 px-3 pb-3 pt-2 sm:max-h-[min(60dvh,22rem)] sm:px-4 sm:pb-4 sm:pt-3">
        <h1 className="text-base font-semibold tracking-tight text-slate-900">
          Mapa de urbanismo en Madrid: licencias y planes
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-600">
          Consulta en un solo mapa las obras con licencia, los planes en tramitación y los proyectos
          que pueden transformar tu barrio. Filtra por zona, fecha o tipo de actuación y abre la
          ficha de cada proyecto.
        </p>
        <p className="mt-2 text-xs text-slate-500">
          También puedes{" "}
          <Link href="/boletin" className="font-medium text-[var(--portal-accent)] hover:underline">
            ver qué pasa cerca de tu dirección
          </Link>
          {" o consultar "}
          <Link
            href="/madrid/estadisticas"
            className="font-medium text-[var(--portal-accent)] hover:underline"
          >
            estadísticas por barrio
          </Link>
          .
        </p>
        <SeoFaq items={[...EXPLORE_FAQ]} />
      </div>
    </details>
  );
}
