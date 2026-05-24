import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { sigmaClassificationLabel } from "@/lib/sigma-classification";

export type SigmaMapClassificationRow = {
  tipoLegal: string | null;
  escala: string | null;
  contenidoPrincipal: string | null;
  faseNormalizada: string | null;
  categoriaProyecto: string | null;
  confianza?: string | null;
};

export type SigmaClassificationAxisId =
  | "categoriaProyecto"
  | "tipoLegal"
  | "escala"
  | "contenidoPrincipal"
  | "faseNormalizada";

export type SigmaClassificationFilters = Record<SigmaClassificationAxisId, Set<string>>;

export const SIGMA_CLASSIFICATION_AXIS_ORDER: {
  id: SigmaClassificationAxisId;
  label: string;
  defaultOpen?: boolean;
}[] = [
  { id: "categoriaProyecto", label: "Categoría", defaultOpen: true },
  { id: "tipoLegal", label: "Tipo legal" },
  { id: "escala", label: "Escala" },
  { id: "contenidoPrincipal", label: "Contenido" },
  { id: "faseNormalizada", label: "Fase" },
];

export type MadridSigmaClasificacionFile = {
  generatedAt?: string;
  count?: number;
  byExpediente?: Record<string, SigmaMapClassificationRow>;
};

export type SigmaClassificationAxisOption = {
  value: string;
  count: number;
  label: string;
};

export type SigmaClassificationAxisMeta = {
  options: Record<SigmaClassificationAxisId, SigmaClassificationAxisOption[]>;
  totals: Record<SigmaClassificationAxisId, number>;
};

export function sigmaExpedienteKeyFromFeatureProps(
  props: Record<string, unknown>,
): string | null {
  const raw = props.EXP_TX_NUMERO ?? props.expedienteGrupo ?? props.expediente_grupo;
  if (!raw) return null;
  return expedienteGrupoKeyFromVariant(String(raw));
}

export function sigmaClassificationFilterLabel(value: string): string {
  return sigmaClassificationLabel(value) ?? value.replace(/_/g, " ");
}

/** Precalcula opciones y conteos por eje (una pasada sobre el índice). */
export function buildSigmaClassificationAxisMeta(
  index: Record<string, SigmaMapClassificationRow>,
): SigmaClassificationAxisMeta {
  const options = {} as SigmaClassificationAxisMeta["options"];
  const totals = {} as SigmaClassificationAxisMeta["totals"];

  for (const axis of SIGMA_CLASSIFICATION_AXIS_ORDER) {
    const counts = new Map<string, number>();
    for (const row of Object.values(index)) {
      const value = row[axis.id];
      if (!value) continue;
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    options[axis.id] = [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es"))
      .map(([value, count]) => ({
        value,
        count,
        label: sigmaClassificationFilterLabel(value),
      }));
    totals[axis.id] = options[axis.id].length;
  }

  return { options, totals };
}

export function allSigmaClassificationEnabled(
  meta: SigmaClassificationAxisMeta,
): SigmaClassificationFilters {
  const out = {} as SigmaClassificationFilters;
  for (const axis of SIGMA_CLASSIFICATION_AXIS_ORDER) {
    out[axis.id] = new Set(meta.options[axis.id].map((o) => o.value));
  }
  return out;
}

export function isSigmaClassificationFilterActive(
  enabled: SigmaClassificationFilters,
  totals: Record<SigmaClassificationAxisId, number>,
): boolean {
  return SIGMA_CLASSIFICATION_AXIS_ORDER.some((axis) => {
    const total = totals[axis.id];
    if (total === 0) return false;
    const sel = enabled[axis.id];
    return sel.size > 0 && sel.size < total;
  });
}

/** Set de expedientes que pasan el filtro. Null = sin filtro activo. */
export function buildSigmaClassificationAllowedSet(
  index: Record<string, SigmaMapClassificationRow>,
  enabled: SigmaClassificationFilters,
  totals: Record<SigmaClassificationAxisId, number>,
): Set<string> | null {
  if (!isSigmaClassificationFilterActive(enabled, totals)) return null;

  const allowed = new Set<string>();
  for (const [grupo, row] of Object.entries(index)) {
    let ok = true;
    for (const axis of SIGMA_CLASSIFICATION_AXIS_ORDER) {
      const total = totals[axis.id];
      const sel = enabled[axis.id];
      if (sel.size >= total) continue;
      if (sel.size === 0) {
        ok = false;
        break;
      }
      const value = row[axis.id];
      if (!value || !sel.has(value)) {
        ok = false;
        break;
      }
    }
    if (ok) allowed.add(grupo);
  }
  return allowed;
}
