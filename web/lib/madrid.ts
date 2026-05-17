/** Municipio Madrid capital (no toda la CM en el BOCM). */
export function isMadridCapital(municipio: string | null | undefined): boolean {
  return (municipio || "").trim().toLowerCase() === "madrid";
}

export function normSearch(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}
