import Link from "next/link";
import { SeoDetailsBlock, SeoFaq } from "@/components/seo/SeoFaq";

const BOLETIN_FAQ = [
  {
    q: "¿Qué puedo ver cerca de mi dirección?",
    a: "Obras con licencia recientes y planes urbanísticos en tramitación en un radio que tú eliges — desde la manzana hasta el barrio. Si alguna actuación afecta directamente a tu edificio, lo indicamos.",
  },
  {
    q: "¿Necesito saber datos técnicos de mi edificio?",
    a: "No. Escribe calle y número o elige una sugerencia del buscador. Si la dirección no está en nuestra base, intentamos localizarla dentro de Madrid capital.",
  },
  {
    q: "¿De dónde salen los datos?",
    a: "De registros públicos del Ayuntamiento de Madrid: licencias de obra y expedientes de planeamiento. Homes no sustituye al consistorio; enlaza siempre a las fuentes oficiales.",
  },
  {
    q: "¿Cómo sé si van a construir cerca de mi casa?",
    a: "Genera el resumen con un radio amplio y revisa la cronología de novedades. Para más contexto, abre la ficha de tu edificio o el mapa completo de la ciudad.",
  },
] as const;

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
