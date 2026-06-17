import Link from "next/link";
import { SeoDetailsBlock, SeoFaq } from "@/components/seo/SeoFaq";
import { BOLETIN_FAQ } from "@/lib/seo-faq-content";

export function BoletinPageSeoFaq() {
  return (
    <SeoDetailsBlock summary="Preguntas frecuentes sobre licencias y planes en tu zona">
      <p className="text-sm leading-relaxed text-slate-600">
        Esta herramienta resume qué obras y planes hay alrededor de una dirección en Madrid: licencias
        concedidas, reformas en curso y proyectos de transformación del barrio. Para ver toda la
        ciudad, abre el{" "}
        <Link href="/explore" className="font-medium text-[var(--portal-accent)] hover:underline">
          mapa de urbanismo
        </Link>
        .
      </p>
      <SeoFaq items={[...BOLETIN_FAQ]} />
    </SeoDetailsBlock>
  );
}
