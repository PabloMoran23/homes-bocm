/** Vigencia general de la Ordenanza 6/2022 (licencias y DR urbanísticas). */
export const ORDENANZA_LICENCIAS_2022 = {
  year: 2022,
  monthKey: "2022-06",
  monthLabel: "jun 22",
  label: "Ordenanza 6/2022",
} as const;

/** Primer año con etiquetado homogéneo en datos abiertos (gráfico de actuaciones). */
export const LICENCIAS_DETALLE_MIN_YEAR = 2023;
export const LICENCIAS_DETALLE_MIN_MONTH = `${LICENCIAS_DETALLE_MIN_YEAR}-01`;

/** Aviso principal del panel de licencias (contexto legal + etiquetado open data). */
export const LICENCIAS_DASHBOARD_NOTA =
  "Desde junio de 2022 rige la Ordenanza 6/2022 de licencias y declaraciones responsables. Los totales en datos abiertos bajan de forma visible a partir de 2022–2023 y el Ayuntamiento etiqueta los expedientes de otro modo (menos comunicación previa, tipos LU/DR más explícitos). Las cifras anuales antes y después no son directamente comparable.";
