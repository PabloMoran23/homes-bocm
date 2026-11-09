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
    a: "Proyectos con ubicación identificada cerca de una dirección y contexto del municipio cuando no disponemos de esa precisión. En Madrid capital también puedes consultar licencias. Cada vista indica el alcance y la cobertura de las fuentes.",
  },
  {
    q: "¿Necesito saber datos técnicos de mi edificio?",
    a: "No. Escribe calle y número o elige una sugerencia del buscador. Puedes buscar direcciones de España; el contenido depende de los municipios y las fuentes que tenemos disponibles.",
  },
  {
    q: "¿De dónde salen los datos?",
    a: "De registros y portales municipales y boletines oficiales. La cobertura varía entre municipios. Las fichas enlazan las fuentes; no tener registros en Homes no significa que no existan proyectos u obras.",
  },
  {
    q: "¿Cómo sé si van a construir cerca de mi casa?",
    a: "Genera el resumen con un radio amplio y revisa la cronología de novedades. Para más contexto, abre la ficha de tu edificio o el mapa completo de la ciudad.",
  },
];
