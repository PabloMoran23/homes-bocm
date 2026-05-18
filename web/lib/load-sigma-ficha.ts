import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import { sigmaFichaGrupoFromSlug } from "@/lib/sigma-ficha-path";
import type { SigmaBocmPopupLink } from "@/lib/sector-geo";
import type {
  MadridSigmaDataset,
  SigmaExpediente,
  SigmaFicha,
  SigmaVisorFicha,
  SigmaVisorNtiDoc,
  SigmaVisorTramite,
} from "@/lib/types";

type VisoRecord = {
  sinDatosVisor?: boolean;
  visorUrlUsada?: string;
  visorCabecera?: { h1?: string; h2?: string };
  visorFicha?: SigmaVisorFicha;
  tramitacion?: SigmaVisorTramite[];
  documentacionUrls?: string[];
  ntiListadoUrl?: string;
  ntiDocumentosTotal?: number;
  ntiDocumentosMuestra?: SigmaVisorNtiDoc[];
  ntiArbol?: {
    documentosTotal?: number;
    documentos?: SigmaVisorNtiDoc[];
    documentosMuestra?: SigmaVisorNtiDoc[];
  };
};

type VisoBundle = {
  generatedAt?: string;
  byGrupoExpediente?: Record<string, VisoRecord>;
};

let catalogPromise: Promise<{
  byGrupo: Map<string, SigmaExpediente>;
  syncAt: string | null;
}> | null = null;

let visoPromise: Promise<{
  byGrupo: Record<string, VisoRecord>;
  generatedAt: string | null;
}> | null = null;

let bocmPromise: Promise<Record<string, SigmaBocmPopupLink[]>> | null = null;

async function loadCatalog(): Promise<{
  byGrupo: Map<string, SigmaExpediente>;
  syncAt: string | null;
}> {
  if (!catalogPromise) {
    catalogPromise = (async () => {
      const raw = await fetchStaticJson<MadridSigmaDataset>("/data/madrid-sigma.json");
      const byGrupo = new Map<string, SigmaExpediente>();
      if (!raw) return { byGrupo, syncAt: null };
      for (const e of raw.expedientes || []) {
        const n = e.EXP_TX_NUMERO;
        if (!n) continue;
        byGrupo.set(expedienteGrupoKeyFromVariant(String(n)), e);
      }
      return { byGrupo, syncAt: raw.generatedAt ?? null };
    })();
  }
  return catalogPromise;
}

async function loadViso(): Promise<{
  byGrupo: Record<string, VisoRecord>;
  generatedAt: string | null;
}> {
  if (!visoPromise) {
    visoPromise = (async () => {
      const raw = await fetchStaticJson<VisoBundle>("/data/madrid-sigma-visor-slim.json");
      if (!raw?.byGrupoExpediente) {
        return { byGrupo: {}, generatedAt: null };
      }
      return {
        byGrupo: raw.byGrupoExpediente,
        generatedAt: raw.generatedAt ?? null,
      };
    })();
  }
  return visoPromise;
}

async function loadBocmLinks(): Promise<Record<string, SigmaBocmPopupLink[]>> {
  if (!bocmPromise) {
    bocmPromise = (async () => {
      const raw = await fetchStaticJson<{ byExpediente?: Record<string, SigmaBocmPopupLink[]> }>(
        "/data/madrid-sigma-bocm-projects.json",
      );
      return raw?.byExpediente || {};
    })();
  }
  return bocmPromise;
}

function parseViso(v: VisoRecord | undefined, generatedAt: string | null) {
  if (!v || v.sinDatosVisor) {
    return {
      visorFetchedAt: generatedAt,
      visorUrl: null as string | null,
      visorCabecera: null,
      visorFicha: null,
      tramitacion: [] as SigmaVisorTramite[],
      documentacionUrls: [] as string[],
      ntiListadoUrl: null as string | null,
      ntiDocumentosTotal: null as number | null,
      ntiDocumentosMuestra: [] as SigmaVisorNtiDoc[],
    };
  }
  const nti = v.ntiArbol;
  const ntiDocs = Array.isArray(v.ntiDocumentosMuestra)
    ? v.ntiDocumentosMuestra
    : nti && Array.isArray(nti.documentos) && nti.documentos.length
      ? nti.documentos
      : nti && Array.isArray(nti.documentosMuestra)
        ? nti.documentosMuestra
        : [];
  const ntiTotal =
    typeof v.ntiDocumentosTotal === "number"
      ? v.ntiDocumentosTotal
      : nti && typeof nti.documentosTotal === "number"
        ? nti.documentosTotal
        : null;
  return {
    visorFetchedAt: generatedAt,
    visorUrl: v.visorUrlUsada?.trim() || null,
    visorCabecera: v.visorCabecera
      ? { h1: v.visorCabecera.h1 ?? null, h2: v.visorCabecera.h2 ?? null }
      : null,
    visorFicha: v.visorFicha ?? null,
    tramitacion: Array.isArray(v.tramitacion) ? v.tramitacion : [],
    documentacionUrls: Array.isArray(v.documentacionUrls) ? v.documentacionUrls : [],
    ntiListadoUrl: v.ntiListadoUrl?.trim() || null,
    ntiDocumentosTotal: ntiTotal,
    ntiDocumentosMuestra: ntiDocs.slice(0, 80),
  };
}

export async function loadSigmaFichaBySlug(slug: string): Promise<SigmaFicha | null> {
  const grupo = sigmaFichaGrupoFromSlug(slug);
  const [{ byGrupo: cat, syncAt }, { byGrupo: viso, generatedAt }, bocm] = await Promise.all([
    loadCatalog(),
    loadViso(),
    loadBocmLinks(),
  ]);
  const catalog = cat.get(grupo) ?? null;
  const visoParsed = parseViso(viso[grupo], generatedAt);
  const bocmProyectos = bocm[grupo] || [];

  if (!catalog && !visoParsed.tramitacion.length && !visoParsed.ntiDocumentosTotal && !bocmProyectos.length) {
    return null;
  }

  return {
    expedienteGrupo: grupo,
    sigmaSyncAt: syncAt,
    catalog,
    bocmProyectos,
    ...visoParsed,
  };
}

/** Lista slugs para sitemap o pruebas (opcional). */
export async function listSigmaFichaSlugs(): Promise<string[]> {
  const [{ byGrupo: cat }, { byGrupo: viso }] = await Promise.all([loadCatalog(), loadViso()]);
  const keys = new Set<string>([...cat.keys(), ...Object.keys(viso)]);
  return [...keys].map((g) => g.replace(/\//g, "-")).sort();
}
