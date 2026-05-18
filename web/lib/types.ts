export type SigmaBocmLink = {
  id: string;
  title: string;
  bocmDate: string;
  artNum?: string | null;
  esRelevante?: boolean | null;
};

export type SigmaBoletinMencion = {
  projectId: string;
  bocmDate: string;
  artNum: string;
  title: string;
  estadoTramitacion: string | null;
  tipoInstrumento: string | null;
  esRelevante: boolean | null;
  pdfUrl: string | null;
  mismoAnuncioQueEstaVista: boolean;
};

export type SigmaVisorTramite = {
  fecha: string | null;
  tramite: string | null;
  organo: string | null;
};

export type SigmaVisorNtiDoc = {
  rutaCarpetas: string;
  titulo: string | null;
  tooltip: string | null;
  url: string;
  fechaCreacion: string | null;
  tipodocNti: string | null;
  fechaDocumento: string | null;
};

/** Campos estructurados de la ficha HTML del visor municipal (VSURB). */
export type SigmaVisorFicha = {
  figuraCodigo?: string | null;
  denominacionVisor?: string | null;
  figuraTipo?: string | null;
  tipoPlaneamiento?: string | null;
  expedienteVisor?: string | null;
  archivoPlanos?: string | null;
  ambitoOrdenacion?: string | null;
  distrito?: string | null;
  iniciativa?: string | null;
  sistemaActuacion?: string | null;
  promotor?: string | null;
  unidadTramitadora?: string | null;
  descripcionAmbito?: string | null;
  resumenContenido?: string | null;
  observaciones?: string | null;
  alegaciones?: string | null;
  equipoRedactor?: string | null;
  sugerencias?: string | null;
  superficieAmbitoTexto?: string | null;
  superficieAmbitoM2?: number | null;
};

export type Project = {
  id: string;
  sourceId: string;
  sourceLabel: string;
  territorioId: string;
  territorioLabel: string;
  bocmDate: string;
  artNum: string;
  title: string;
  pdfUrl: string | null;
  municipio: string;
  tipoInstrumento: string;
  nombreSector: string;
  estadoTramitacion: string;
  fechaAcuerdo: string | null;
  organo: string;
  promotor: string | null;
  numViviendas: number | null;
  supTotalM2: number | null;
  supEdificableM2: number | null;
  tipoVivienda: string | null;
  resumen: string;
  municipioProvincia: string;
  categoriasTematicas: string | null;
  economicoResumen: string | null;
  procedimientoExpediente: string | null;
  procedimientoTipo: string | null;
  importeTotalEur: number | null;
  requiereSegundaPasada: boolean;
  charsTextoTotal: number | null;
  lat: number | null;
  lng: number | null;
  /** Clave estable (sector_geometry); enlaza con sector-geometries.geojson */
  sectorKey?: string | null;
  /** Clave legacy (sin boletin_source_id); coincide con stable_key del GeoJSON exportado */
  sectorGeoKey?: string | null;
  coordSource?: string | null;
  /** true | false | null (sin clasificar en CSV) */
  esRelevante?: boolean | null;
  parseError?: string | null;
  sigmaMatchType?: string | null;
  sigmaMatchScore?: number | null;
  sigmaExpediente?: string | null;
  sigmaDenominacion?: string | null;
  sigmaFase?: string | null;
  sigmaEnlace?: string | null;
  sigmaEnIp?: boolean;

  /** Campos sincronizados desde catálogo SIGMA (Ayto.). `sigmaCatalogSyncedAt` = fecha generación índice. */
  sigmaCatalogSyncedAt?: string | null;
  sigmaFiguraCodigo?: string | null;
  sigmaTipoFigura?: string | null;
  sigmaOrganoTramitador?: string | null;
  sigmaCatalogSource?: string | null;
  sigmaSigmaLayerKind?: string | null;
  sigmaObjectId?: number | null;
  sigmaFechaAprobacion?: string | null;
  sigmaInfopublicaInicio?: string | null;
  sigmaInfopublicaFin?: string | null;
  sigmaHasGeometrySigma?: boolean;

  /** Otras publicaciones BO BOCM (Madrid) que citan el mismo nº expediente; orden fecha desc. */
  sigmaBoletinMismaExpediente?: SigmaBoletinMencion[];

  /** Ficha HTML visor servpub + documentación (NTI o visor documental), vía `madrid_viso_fetch`. */
  sigmaVisorFetchedAt?: string | null;
  sigmaVisorUrl?: string | null;
  sigmaVisorCabecera?: { h1: string | null; h2: string | null } | null;
  sigmaVisorTramitacion?: SigmaVisorTramite[];
  sigmaVisorDocumentacionUrls?: string[];
  sigmaVisorNtiListadoUrl?: string | null;
  sigmaVisorNtiDocumentosTotal?: number | null;
  sigmaVisorNtiDocumentosMuestra?: SigmaVisorNtiDoc[];
};

export type DataSummary = {
  generatedAt: string;
  total: number;
  totalRelevant?: number;
  totalNotRelevant?: number;
  totalRelevanceUnknown?: number;
  dateRange: { min: string | null; max: string | null };
  byMunicipio: { name: string; count: number }[];
  byTipo: { name: string; count: number }[];
  byYear: { year: string; count: number }[];
  byTerritorio: { name: string; count: number }[];
  byTerritorioRelevant?: { name: string; count: number }[];
  bySource: { name: string; count: number }[];
  withCoords?: number;
  /** Coordenadas tomadas del centroide del polígono SIGMA (por nº expediente vinculado). */
  coordsDesdeSigmaPolygon?: { ip: number; ad: number; total: number };
  portal?: { name: string; tagline: string };
};

export type AdminSourceStats = {
  sourceId: string;
  territorioId: string;
  territorioLabel: string;
  indexPdfCount: number | null;
  csvRows: number;
  inWeb: number;
  relevant: number;
  notRelevant: number;
  relevanceUnknown: number;
  withMunicipio: number;
  withSector: number;
  withCoords: number;
  parseErrors: number;
  indexGap: number | null;
  parseCoveragePct: number | null;
  relevantPct: number | null;
  sectorPct: number | null;
  coordsPct: number | null;
};

export type AdminGap = {
  priority: "high" | "medium" | "low";
  sourceId: string;
  territorioLabel: string;
  label: string;
  detail: string;
};

export type MadridCapitalBlock = {
  note: string;
  bocmFilasWeb: number;
  bocmRelevantes: number;
  bocmConSector: number;
  bocmConCoords: number;
  /** Madrid capital: proyecto con centroide desde polígono SIGMA (información pública y/o AD). */
  bocmCoordsDesdeSigmaPoligono?: number;
  bocmCoordsSigmaPoligonoIp?: number;
  bocmCoordsSigmaPoligonoAd?: number;
  /** Expediente detectado en BOCM y coords tomadas del polígono SIGMA. */
  bocmConMatchSigmaConUbicPoligono?: number;
  bocmConMatchSigmaTotal?: number;
  bocmResolverAytoPgoum: number;
  sigmaSyncAt: string | null;
  sigmaExpedientesIp: number | null;
  sigmaSinBocm: number | null;
  bocmMatchSigma: number | null;
  bocmMatchPctRelevantes: number | null;
  samplesSigmaSinBocm: Array<Record<string, unknown>>;
  samplesBocmSinMatch: Array<Record<string, unknown>>;
  syncHint?: string;
};

export type SigmaExpediente = {
  source: "informacion_publica" | "tramitados_ad" | string;
  EXP_TX_NUMERO: string | null;
  EXP_TX_DENOM: string | null;
  FAS_TX_DENOM: string | null;
  FEX_DT_INFOPUB_INI?: string | null;
  FEX_DT_INFOPUB_FIN?: string | null;
  FEX_DT_APROB?: string | null;
  FIG_TX_ETIQ?: string | null;
  TFIG_TX_ABREV?: string | null;
  ORG_TX_DESC?: string | null;
  EXP_ID?: number | string | null;
  Enlace?: string | null;
  sigma_layer_kind?: string | null;
  has_geometry?: boolean;
};

export type MadridSigmaDataset = {
  generatedAt: string;
  note?: string;
  counts?: {
    total: number;
    informacion_publica: number;
    tramitados_ad: number;
    tramitados_gestion?: number;
    tramitados_urbanizacion?: number;
    expedientes_unicos?: number;
    with_geometry: number;
  };
  expedientes: SigmaExpediente[];
};

/** Ficha de producto por expediente SIGMA (con o sin anuncio BOCM en el portal). */
export type SigmaFicha = {
  expedienteGrupo: string;
  sigmaSyncAt: string | null;
  catalog: SigmaExpediente | null;
  visorFetchedAt: string | null;
  visorUrl: string | null;
  visorCabecera: { h1: string | null; h2: string | null } | null;
  visorFicha: SigmaVisorFicha | null;
  tramitacion: SigmaVisorTramite[];
  documentacionUrls: string[];
  ntiListadoUrl: string | null;
  ntiDocumentosTotal: number | null;
  ntiDocumentosMuestra: SigmaVisorNtiDoc[];
  /** Anuncios BOCM enlazados (0 = ficha sólo SIGMA). */
  bocmProyectos: SigmaBocmLink[];
};

export type PipelineLogSlice = {
  phase: string;
  fetchCurrent: number | null;
  fetchTotal: number | null;
  lastLines: string[];
  errorLineCount: number;
  errorSample: string[];
  logPath?: string;
  logBytes?: number;
  logMtime?: string;
};

export type PipelineProcesses = {
  visorFetchRunning: boolean;
  downloadRunning?: boolean;
  pipelineScriptRunning?: boolean;
  visorFetchSample?: string | null;
};

export type MadridLicenciaRow = {
  anioDataset: number | null;
  fechaAlta: string | null;
  fechaConcesion: string | null;
  procedimiento: string | null;
  tipoExpediente: string | null;
  uso: string | null;
  distrito: string | null;
  barrio: string | null;
  direccion: string | null;
  interesado: string | null;
  objeto: string | null;
  unidad: string | null;
  ndpEdificio: number | string | null;
  lat: number | null;
  lng: number | null;
};

export type MadridLicenciasIndex = {
  generatedAt: string;
  source: string;
  totalRows: number;
  withCoords: number;
  byYear: Record<string, number>;
  years: number[];
  topUso: { name: string; count: number }[];
  topDistrito: { name: string; count: number }[];
  topProcedimiento: { name: string; count: number }[];
};

export type PipelineStatusPayload = {
  generatedAt: string;
  pocRoot: string;
  sqlite: Record<string, unknown>;
  visorJson: Record<string, unknown>;
  log: PipelineLogSlice;
  processes?: PipelineProcesses;
  error?: string;
};

export type AdminCoverage = {
  generatedAt: string;
  totals: {
    indexPdfCount: number;
    csvRows: number;
    inWeb: number;
    relevant: number;
    notRelevant: number;
    relevanceUnknown: number;
    withCoords: number;
    indexGap: number;
  };
  sources: AdminSourceStats[];
  gaps: AdminGap[];
  madridCapital?: MadridCapitalBlock;
};
