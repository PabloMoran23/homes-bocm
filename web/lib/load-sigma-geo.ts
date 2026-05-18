import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import type { SectorFeatureCollection } from "@/lib/sector-geo";

function layerGeoUrl(kind: string | null | undefined, source: string | null | undefined): string[] {
  const urls: string[] = [];
  const k = kind || source;
  if (k === "tramitados_ad" || source === "tramitados_ad") {
    urls.push("/data/madrid-sigma-ad.geojson");
  } else if (k === "tramitados_gestion" || source === "tramitados_gestion") {
    urls.push("/data/madrid-sigma-gestion.geojson");
  } else if (k === "tramitados_urbanizacion" || source === "tramitados_urbanizacion") {
    urls.push("/data/madrid-sigma-urbanizacion.geojson");
  } else {
    urls.push("/data/madrid-sigma-ip.geojson");
  }
  urls.push("/data/madrid-sigma-ambitos.geojson");
  return urls;
}

function filterFeaturesForExpediente(
  fc: SectorFeatureCollection,
  expedienteGrupo: string,
): SectorFeatureCollection["features"] {
  const target = expedienteGrupoKeyFromVariant(expedienteGrupo);
  return fc.features.filter((f) => {
    const n = String((f.properties as Record<string, unknown>)?.EXP_TX_NUMERO || "");
    return expedienteGrupoKeyFromVariant(n) === target;
  });
}

/** Carga polígono(s) SIGMA del expediente (capa específica + fallback ámbitos). */
export async function fetchSigmaGeoForExpediente(
  expedienteGrupo: string,
  opts?: { layerKind?: string | null; source?: string | null; signal?: AbortSignal },
): Promise<SectorFeatureCollection | null> {
  const urls = layerGeoUrl(opts?.layerKind, opts?.source ?? null);
  for (const url of urls) {
    try {
      const res = await fetch(url, { signal: opts?.signal });
      if (!res.ok) continue;
      const fc = (await res.json()) as SectorFeatureCollection;
      const feats = filterFeaturesForExpediente(fc, expedienteGrupo);
      if (feats.length) {
        return { type: "FeatureCollection", features: feats };
      }
    } catch {
      /* siguiente fuente */
    }
  }
  return null;
}
