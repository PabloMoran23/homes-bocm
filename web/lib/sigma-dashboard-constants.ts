/** Cuatro ejes principales de clasificación automática (visor + modelo). */
export const SIGMA_DASHBOARD_PRIMARY_AXES = [
  { id: "categoriaProyecto" as const, label: "Categoría del proyecto" },
  { id: "tipoObra" as const, label: "Tipo de obra" },
  { id: "tipoLegal" as const, label: "Instrumento" },
  { id: "escala" as const, label: "Escala del ámbito" },
];

export const SIGMA_DASHBOARD_NOTA =
  "Cada proyecto urbanístico se enriquece con la ficha pública del Ayuntamiento de Madrid (promotor, distrito, objeto del plan, tramitación, superficie…). " +
  "Sobre ese texto aplicamos una clasificación automática en cuatro ejes —categoría, tipo de obra, instrumento y escala— para comparar proyectos de forma homogénea. " +
  "La fase que muestra el registro municipal puede diferir ligeramente de la fase normalizada del clasificador.";
