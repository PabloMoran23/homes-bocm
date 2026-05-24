import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";
import { fetchStaticJson } from "@/lib/fetch-static-json";
import { normalizeResumenContenido, resumenContenidoFromVisorFicha } from "@/lib/normalize-resumen-contenido";
import { sigmaFichaGrupoFromSlug } from "@/lib/sigma-ficha-path";
import { getSupabaseServer } from "@/lib/supabase/server";
import type { SigmaBocmPopupLink } from "@/lib/sector-geo";
import type { SigmaClassification } from "@/lib/sigma-classification";
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

type SupabaseCatalogRow = {
  expediente_grupo: string;
  exp_numero_original: string | null;
  sigma_layer_kind: string | null;
  denominacion: string | null;
  fase: string | null;
  fecha_aprob: string | null;
  infopublica_inicio: string | null;
  infopublica_fin: string | null;
  figura_codigo: string | null;
  tipo_figura: string | null;
  organo_tramitador: string | null;
  enlace: string | null;
  catalog_source: string | null;
  object_id: number | string | null;
  has_geometry: boolean | null;
  synced_at: string | null;
};

type SupabaseVisorRow = {
  sin_datos_visor: boolean | null;
  visor_url: string | null;
  visor_cabecera: VisoRecord["visorCabecera"] | null;
  visor_ficha: SigmaVisorFicha | null;
  tramitacion: SigmaVisorTramite[] | null;
  documentacion_urls: string[] | null;
  nti_listado_url: string | null;
  nti_documentos_total: number | null;
  nti_documentos_muestra: SigmaVisorNtiDoc[] | null;
  fetched_at: string | null;
  resumen_contenido: string | null;
  tipo_legal: string | null;
  escala: string | null;
  contenido_principal: string | null;
  fase_normalizada: string | null;
  categoria_proyecto: string | null;
  tipo_obra: string | null;
  clasificacion_confianza: string | null;
  clasificacion_fuentes: Record<string, unknown> | null;
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

function mergeVisorFicha(
  ficha: SigmaVisorFicha | null | undefined,
  resumenContenido: string | null,
): SigmaVisorFicha | null {
  if (!ficha && !resumenContenido) return null;
  if (!ficha) return { resumenContenido };
  return {
    ...ficha,
    resumenContenido: resumenContenido ?? normalizeResumenContenido(ficha.resumenContenido),
  };
}

function parseViso(v: VisoRecord | undefined, generatedAt: string | null) {
  if (!v || v.sinDatosVisor) {
    return {
      visorFetchedAt: generatedAt,
      visorUrl: null as string | null,
      visorCabecera: null,
      visorFicha: null as SigmaVisorFicha | null,
      resumenContenido: null as string | null,
      clasificacion: null as SigmaClassification | null,
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
  const resumenContenido = resumenContenidoFromVisorFicha(v.visorFicha);
  return {
    visorFetchedAt: generatedAt,
    visorUrl: v.visorUrlUsada?.trim() || null,
    visorCabecera: v.visorCabecera
      ? { h1: v.visorCabecera.h1 ?? null, h2: v.visorCabecera.h2 ?? null }
      : null,
    visorFicha: mergeVisorFicha(v.visorFicha ?? null, resumenContenido),
    resumenContenido,
    clasificacion: null as SigmaClassification | null,
    tramitacion: Array.isArray(v.tramitacion) ? v.tramitacion : [],
    documentacionUrls: Array.isArray(v.documentacionUrls) ? v.documentacionUrls : [],
    ntiListadoUrl: v.ntiListadoUrl?.trim() || null,
    ntiDocumentosTotal: ntiTotal,
    ntiDocumentosMuestra: ntiDocs.slice(0, 80),
  };
}

function catalogFromSupabase(row: SupabaseCatalogRow | null): SigmaExpediente | null {
  if (!row) return null;
  return {
    source: row.catalog_source || row.sigma_layer_kind || "supabase",
    EXP_TX_NUMERO: row.exp_numero_original || row.expediente_grupo,
    EXP_TX_DENOM: row.denominacion,
    FAS_TX_DENOM: row.fase,
    FEX_DT_APROB: row.fecha_aprob,
    FEX_DT_INFOPUB_INI: row.infopublica_inicio,
    FEX_DT_INFOPUB_FIN: row.infopublica_fin,
    FIG_TX_ETIQ: row.figura_codigo,
    TFIG_TX_ABREV: row.tipo_figura,
    ORG_TX_DESC: row.organo_tramitador,
    EXP_ID: row.object_id,
    Enlace: row.enlace,
    sigma_layer_kind: row.sigma_layer_kind,
    has_geometry: row.has_geometry === true,
  };
}

function parseSupabaseVisor(row: SupabaseVisorRow | null) {
  if (!row || row.sin_datos_visor) {
    return {
      visorFetchedAt: row?.fetched_at ?? null,
      visorUrl: null as string | null,
      visorCabecera: null,
      visorFicha: null as SigmaVisorFicha | null,
      resumenContenido: normalizeResumenContenido(row?.resumen_contenido),
      clasificacion: null as SigmaClassification | null,
      tramitacion: [] as SigmaVisorTramite[],
      documentacionUrls: [] as string[],
      ntiListadoUrl: null as string | null,
      ntiDocumentosTotal: null as number | null,
      ntiDocumentosMuestra: [] as SigmaVisorNtiDoc[],
    };
  }
  const resumenContenido =
    normalizeResumenContenido(row.resumen_contenido) ??
    resumenContenidoFromVisorFicha(row.visor_ficha);
  return {
    visorFetchedAt: row.fetched_at ?? null,
    visorUrl: row.visor_url?.trim() || null,
    visorCabecera: row.visor_cabecera
      ? { h1: row.visor_cabecera.h1 ?? null, h2: row.visor_cabecera.h2 ?? null }
      : null,
    visorFicha: mergeVisorFicha(row.visor_ficha, resumenContenido),
    resumenContenido,
    clasificacion: clasificacionFromRow(row),
    tramitacion: Array.isArray(row.tramitacion) ? row.tramitacion : [],
    documentacionUrls: Array.isArray(row.documentacion_urls) ? row.documentacion_urls : [],
    ntiListadoUrl: row.nti_listado_url?.trim() || null,
    ntiDocumentosTotal: row.nti_documentos_total ?? null,
    ntiDocumentosMuestra: Array.isArray(row.nti_documentos_muestra)
      ? row.nti_documentos_muestra.slice(0, 80)
      : [],
  };
}

function clasificacionFromRow(row: {
  tipo_legal?: string | null;
  escala?: string | null;
  contenido_principal?: string | null;
  fase_normalizada?: string | null;
  categoria_proyecto?: string | null;
  tipo_obra?: string | null;
  clasificacion_confianza?: string | null;
  clasificacion_fuentes?: Record<string, unknown> | null;
} | null | undefined): SigmaClassification | null {
  if (!row?.categoria_proyecto) return null;
  return {
    tipoLegal: row.tipo_legal ?? null,
    escala: row.escala ?? null,
    contenidoPrincipal: row.contenido_principal ?? null,
    faseNormalizada: row.fase_normalizada ?? null,
    categoriaProyecto: row.categoria_proyecto,
    tipoObra: row.tipo_obra ?? null,
    confianza: row.clasificacion_confianza ?? null,
    fuentes: row.clasificacion_fuentes ?? null,
  };
}

type SigmaFichaRpcPayload = {
  catalog: SupabaseCatalogRow | null;
  visor: SupabaseVisorRow | null;
  bocm: Array<{
    id: string;
    title: string;
    bocmDate: string;
    artNum: string;
    esRelevante: boolean | null;
  }> | null;
};

async function loadClasificacionFromRpc(grupo: string): Promise<SigmaClassification | null> {
  const supabase = getSupabaseServer();
  if (!supabase) return null;
  const { data, error } = await supabase.rpc("get_sigma_clasificacion", {
    p_expediente_grupo: grupo,
  });
  if (error) {
    console.warn("get_sigma_clasificacion:", error.message);
    return null;
  }
  return clasificacionFromRow(data as SupabaseVisorRow | null);
}

async function loadSigmaFichaFromSupabase(grupo: string): Promise<SigmaFicha | null> {
  const supabase = getSupabaseServer();
  if (!supabase) return null;

  const { data, error } = await supabase.rpc("get_sigma_ficha", {
    p_expediente_grupo: grupo,
  });
  if (error) {
    console.warn("get_sigma_ficha:", error.message);
    return null;
  }
  if (!data) return null;

  const payload = data as SigmaFichaRpcPayload;
  const visorParsed = parseSupabaseVisor(payload.visor ?? null);
  const bocmProyectos = Array.isArray(payload.bocm)
    ? payload.bocm
        .filter((b) => b?.id)
        .map(
          (b): SigmaBocmPopupLink => ({
            id: String(b.id),
            title: String(b.title || "").slice(0, 220),
            bocmDate: String(b.bocmDate || ""),
            artNum: String(b.artNum || ""),
            esRelevante: typeof b.esRelevante === "boolean" ? b.esRelevante : null,
          }),
        )
    : [];

  if (
    !payload.catalog &&
    !visorParsed.tramitacion.length &&
    !visorParsed.ntiDocumentosTotal &&
    !visorParsed.resumenContenido &&
    !bocmProyectos.length
  ) {
    return null;
  }

  return {
    expedienteGrupo: grupo,
    sigmaSyncAt: payload.catalog?.synced_at ?? null,
    catalog: catalogFromSupabase(payload.catalog ?? null),
    bocmProyectos,
    ...visorParsed,
  };
}

type VisorParsed = ReturnType<typeof parseViso>;

function mergeVisorLayers(primary: VisorParsed, fallback: VisorParsed): VisorParsed {
  const resumenContenido = primary.resumenContenido ?? fallback.resumenContenido;
  const visorFicha = mergeVisorFicha(primary.visorFicha ?? fallback.visorFicha, resumenContenido);
  return {
    visorFetchedAt: primary.visorFetchedAt ?? fallback.visorFetchedAt,
    visorUrl: primary.visorUrl ?? fallback.visorUrl,
    visorCabecera: primary.visorCabecera ?? fallback.visorCabecera,
    resumenContenido,
    visorFicha,
    clasificacion: primary.clasificacion ?? fallback.clasificacion,
    tramitacion: primary.tramitacion.length ? primary.tramitacion : fallback.tramitacion,
    documentacionUrls: primary.documentacionUrls.length
      ? primary.documentacionUrls
      : fallback.documentacionUrls,
    ntiListadoUrl: primary.ntiListadoUrl ?? fallback.ntiListadoUrl,
    ntiDocumentosTotal: primary.ntiDocumentosTotal ?? fallback.ntiDocumentosTotal,
    ntiDocumentosMuestra: primary.ntiDocumentosMuestra.length
      ? primary.ntiDocumentosMuestra
      : fallback.ntiDocumentosMuestra,
  };
}

function pickVisorParsed(ficha: SigmaFicha): VisorParsed {
  return {
    visorFetchedAt: ficha.visorFetchedAt,
    visorUrl: ficha.visorUrl,
    visorCabecera: ficha.visorCabecera,
    visorFicha: ficha.visorFicha,
    resumenContenido: ficha.resumenContenido,
    clasificacion: ficha.clasificacion,
    tramitacion: ficha.tramitacion,
    documentacionUrls: ficha.documentacionUrls,
    ntiListadoUrl: ficha.ntiListadoUrl,
    ntiDocumentosTotal: ficha.ntiDocumentosTotal,
    ntiDocumentosMuestra: ficha.ntiDocumentosMuestra,
  };
}

export async function loadSigmaFichaBySlug(slug: string): Promise<SigmaFicha | null> {
  const grupo = sigmaFichaGrupoFromSlug(slug);
  const [{ byGrupo: cat, syncAt }, { byGrupo: viso, generatedAt }, bocm, fromSupabase] =
    await Promise.all([
      loadCatalog(),
      loadViso(),
      loadBocmLinks(),
      loadSigmaFichaFromSupabase(grupo),
    ]);
  const staticVisor = parseViso(viso[grupo], generatedAt);
  const staticCatalog = cat.get(grupo) ?? null;
  const staticBocm = bocm[grupo] || [];

  if (fromSupabase) {
    const mergedVisor = mergeVisorLayers(pickVisorParsed(fromSupabase), staticVisor);
    const clasificacion =
      mergedVisor.clasificacion ?? (await loadClasificacionFromRpc(grupo));
    return {
      ...fromSupabase,
      ...mergedVisor,
      clasificacion,
      catalog: fromSupabase.catalog ?? staticCatalog,
      bocmProyectos: fromSupabase.bocmProyectos.length ? fromSupabase.bocmProyectos : staticBocm,
    };
  }

  if (
    !staticCatalog &&
    !staticVisor.tramitacion.length &&
    !staticVisor.ntiDocumentosTotal &&
    !staticVisor.resumenContenido &&
    !staticBocm.length
  ) {
    return null;
  }

  const clasificacion = await loadClasificacionFromRpc(grupo);

  return {
    expedienteGrupo: grupo,
    sigmaSyncAt: syncAt,
    catalog: staticCatalog,
    bocmProyectos: staticBocm,
    ...staticVisor,
    clasificacion,
  };
}

/** Lista slugs para sitemap o pruebas (opcional). */
export async function listSigmaFichaSlugs(): Promise<string[]> {
  const [{ byGrupo: cat }, { byGrupo: viso }] = await Promise.all([loadCatalog(), loadViso()]);
  const keys = new Set<string>([...cat.keys(), ...Object.keys(viso)]);
  return [...keys].map((g) => g.replace(/\//g, "-")).sort();
}
