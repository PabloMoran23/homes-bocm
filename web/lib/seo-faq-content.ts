export type SeoFaqItem = { q: string; a: string };

export const EXPLORE_FAQ: readonly SeoFaqItem[] = [
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
];

export const BOLETIN_FAQ: readonly SeoFaqItem[] = [
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
];
