import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
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

const DATA = join(process.cwd(), "public/data");

type VisoRecord = {
  sinDatosVisor?: boolean;
  visorUrlUsada?: string;
  visorCabecera?: { h1?: string; h2?: string };
  visorFicha?: SigmaVisorFicha;
  tramitacion?: SigmaVisorTramite[];
  documentacionUrls?: string[];
  ntiListadoUrl?: string;
  ntiArbol?: {
    documentosTotal?: number;
    documentos?: SigmaVisorNtiDoc[];
    documentosMuestra?: SigmaVisorNtiDoc[];
  };
};

let catalogByGrupo: Map<string, SigmaExpediente> | null = null;
let catalogSyncAt: string | null = null;
let visoByGrupo: Record<string, VisoRecord> | null = null;
let visoGeneratedAt: string | null = null;
let bocmByExpediente: Record<string, SigmaBocmPopupLink[]> | null = null;

function loadCatalog(): Map<string, SigmaExpediente> {
  if (catalogByGrupo) return catalogByGrupo;
  const path = join(DATA, "madrid-sigma.json");
  if (!existsSync(path)) {
    catalogByGrupo = new Map();
    return catalogByGrupo;
  }
  const raw = JSON.parse(readFileSync(path, "utf-8")) as MadridSigmaDataset;
  catalogSyncAt = raw.generatedAt ?? null;
  catalogByGrupo = new Map();
  for (const e of raw.expedientes || []) {
    const n = e.EXP_TX_NUMERO;
    if (!n) continue;
    catalogByGrupo.set(expedienteGrupoKeyFromVariant(String(n)), e);
  }
  return catalogByGrupo;
}

function loadViso(): { byGrupo: Record<string, VisoRecord>; generatedAt: string | null } {
  if (visoByGrupo) return { byGrupo: visoByGrupo, generatedAt: visoGeneratedAt };
  const path = join(DATA, "madrid-viso-expedientes.json");
  if (!existsSync(path)) {
    visoByGrupo = {};
    return { byGrupo: visoByGrupo, generatedAt: null };
  }
  const raw = JSON.parse(readFileSync(path, "utf-8")) as {
    generatedAt?: string;
    byGrupoExpediente?: Record<string, VisoRecord>;
  };
  visoGeneratedAt = raw.generatedAt ?? null;
  visoByGrupo = raw.byGrupoExpediente || {};
  return { byGrupo: visoByGrupo, generatedAt: visoGeneratedAt };
}

function loadBocmLinks(): Record<string, SigmaBocmPopupLink[]> {
  if (bocmByExpediente) return bocmByExpediente;
  const path = join(DATA, "madrid-sigma-bocm-projects.json");
  if (!existsSync(path)) {
    bocmByExpediente = {};
    return bocmByExpediente;
  }
  const raw = JSON.parse(readFileSync(path, "utf-8")) as {
    byExpediente?: Record<string, SigmaBocmPopupLink[]>;
  };
  bocmByExpediente = raw.byExpediente || {};
  return bocmByExpediente;
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
  const ntiDocs =
    nti && Array.isArray(nti.documentos) && nti.documentos.length
      ? nti.documentos
      : nti && Array.isArray(nti.documentosMuestra)
        ? nti.documentosMuestra
        : [];
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
    ntiDocumentosTotal:
      nti && typeof nti.documentosTotal === "number" ? nti.documentosTotal : null,
    ntiDocumentosMuestra: ntiDocs.slice(0, 80),
  };
}

export function loadSigmaFichaBySlug(slug: string): SigmaFicha | null {
  const grupo = sigmaFichaGrupoFromSlug(slug);
  const catalog = loadCatalog().get(grupo) ?? null;
  const { byGrupo, generatedAt } = loadViso();
  const viso = parseViso(byGrupo[grupo], generatedAt);
  const bocm = loadBocmLinks()[grupo] || [];

  if (!catalog && !viso.tramitacion.length && !viso.ntiDocumentosTotal && !bocm.length) {
    return null;
  }

  return {
    expedienteGrupo: grupo,
    sigmaSyncAt: catalogSyncAt,
    catalog,
    bocmProyectos: bocm,
    ...viso,
  };
}

/** Lista slugs para sitemap o pruebas (opcional). */
export function listSigmaFichaSlugs(): string[] {
  const cat = loadCatalog();
  const { byGrupo } = loadViso();
  const keys = new Set<string>([...cat.keys(), ...Object.keys(byGrupo)]);
  return [...keys].map((g) => g.replace(/\//g, "-")).sort();
}
