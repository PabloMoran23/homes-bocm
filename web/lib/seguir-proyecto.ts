/** Shared rules for the project follow form. Safe to import from server and client. */

export const SEGUIR_POSICIONES = ["cabecera", "documentos", "pie", "barra"] as const;
export type SeguirPosicion = (typeof SEGUIR_POSICIONES)[number];

export const SEGUIR_SEGMENTOS = [
  "Vivo o tengo una propiedad cerca",
  "Busco comprar vivienda",
  "Trabajo en el sector",
  "Invierto",
  "Otro",
] as const;
export type SeguirSegmento = (typeof SEGUIR_SEGMENTOS)[number];

export const SEGUIR_SOURCES = ["project", "boletin", "dashboard"] as const;
export type SeguirSource = (typeof SEGUIR_SOURCES)[number];

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"] as const;

export const SEGUIR_EMAIL_ERROR = "Introduce un correo válido, por ejemplo nombre@correo.com.";
export const SEGUIR_SAVE_ERROR = "No hemos podido guardar tu correo. Inténtalo de nuevo en unos minutos.";
export const SEGUIR_SEGMENT_ERROR = "Tu correo ya está guardado. No hemos podido anotar el motivo; puedes seguir sin responder.";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CONTROL = /[\u0000-\u001f\u007f]/;

export function normalizeEmail(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const email = value.trim().toLowerCase();
  if (email.length < 3 || email.length > 254 || !EMAIL.test(email)) return null;
  return email;
}

export function cleanPosicion(value: unknown): SeguirPosicion | null {
  return typeof value === "string" && (SEGUIR_POSICIONES as readonly string[]).includes(value)
    ? (value as SeguirPosicion)
    : null;
}

export function cleanSegmento(value: unknown): SeguirSegmento | null {
  return typeof value === "string" && (SEGUIR_SEGMENTOS as readonly string[]).includes(value)
    ? (value as SeguirSegmento)
    : null;
}

/** First non-empty place name, capped for the waitlist column. */
export function firstPlaceName(values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    const text = value?.trim();
    if (text && text !== "—") return text.slice(0, 120);
  }
  return null;
}

function cleanPlace(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text || text.length > 120 || CONTROL.test(text)) return null;
  return text;
}

function cleanReferrer(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text || text.length > 300 || /[@?\s]/.test(text) || CONTROL.test(text)) return null;
  if (!/^https?:\/\/[^/?\s]+(?:\/[^\s?]*)?$/.test(text)) return null;
  return text;
}

function cleanUtm(value: unknown): { ok: true; utm: Record<string, string> | null } | { ok: false } {
  if (value == null) return { ok: true, utm: null };
  if (typeof value !== "object" || Array.isArray(value)) return { ok: false };
  const utm: Record<string, string> = {};
  for (const [key, raw] of Object.entries(value)) {
    if (!(UTM_KEYS as readonly string[]).includes(key)) return { ok: false };
    if (typeof raw !== "string") return { ok: false };
    const text = raw.trim();
    if (!text || text.length > 120 || CONTROL.test(text) || text.includes("@")) return { ok: false };
    utm[key] = text;
  }
  return { ok: true, utm: Object.keys(utm).length ? utm : null };
}

export type SeguirAviso = "proyecto" | "zona";

export type SeguirCopy = {
  aviso: SeguirAviso;
  lugar: string | null;
  titulo: string;
  texto: string;
  boton: string;
  botonDocumentos: string;
  barra: string;
  legal: string;
  confirmacion: string;
  pregunta: string;
  ya: string;
};

const CLOSED_FASE = /archiv|desist|caduc|anulad|firme|aprobacion definitiva|aprobado definitivamente/;
const ACTIVE_FASE = /informacion publica|aprobacion inicial|aprobacion provisional|en tramitacion|expediente abierto|incoad|urbanizacion|gestion/;
const PLAN_GENERAL = /plan general|\bpgou\b|normas urbanisticas/;
const INSTRUMENTO_CONCRETO = /modificacion|estudio de detalle|\bplan parcial\b|plan_parcial|\bplan especial\b|plan_especial|reparcelaci|proyecto de urbanizaci|proyecto_urbanizacion|proyecto de actuaci|unidad de ejecucion|delimitacion|enajenacion|catalogacion|\bape\b|\bapr\b/;

function fold(value: string | null | undefined): string {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** A place name fit to read aloud. Codes such as "APE 16.11" are not. */
export function cleanPlaceLabel(value: string | null | undefined): string | null {
  const text = value?.trim().replace(/\s+/g, " ") ?? "";
  if (!text || text === "—" || text.length < 3 || text.length > 80) return null;
  if (!/[a-záéíóúüñ]/i.test(text)) return null;
  if (/^(ape|apr|api|ua|sus|sunp|sg|ed)\b[\s.\d-]*$/i.test(text)) return null;
  if (/^[A-Z0-9.\-\s]{1,14}$/.test(text) && /\d/.test(text)) return null;
  if (/\b(ape|apr|api)\b/i.test(text) && /\d/.test(text)) return null;
  if (/area de planeamiento/.test(fold(text))) return null;
  if (/^(varios|vario|sin datos|no consta)$/i.test(text)) return null;
  return sentencePlace(text);
}

/** District names arrive in capitals («VILLA DE VALLECAS»). */
function sentencePlace(text: string): string {
  if (text !== text.toLocaleUpperCase("es")) return text;
  const small = new Set(["de", "del", "la", "las", "los", "y", "e"]);
  return text
    .toLocaleLowerCase("es")
    .split(" ")
    .map((word, index) => {
      if (index > 0 && small.has(word)) return word;
      return word.charAt(0).toLocaleUpperCase("es") + word.slice(1);
    })
    .join(" ");
}

export function isExpedienteCerrado(input: {
  fase?: string | null;
  faseNormalizada?: string | null;
  estado?: string | null;
}): boolean {
  const norm = fold(input.faseNormalizada).replace(/\s+/g, "_");
  if (norm === "archivado_o_detenido" || norm === "aprobacion_definitiva") return true;
  const text = fold([input.fase, input.estado].filter(Boolean).join(" "));
  if (!text) return false;
  if (ACTIVE_FASE.test(text) && !CLOSED_FASE.test(text)) return false;
  return CLOSED_FASE.test(text);
}

/** The general plan itself, not a modification or a development plan still in process. */
export function isPlanGeneral(texts: Array<string | null | undefined>): boolean {
  const text = fold(texts.filter(Boolean).join(" "));
  if (!text || !PLAN_GENERAL.test(text)) return false;
  if (INSTRUMENTO_CONCRETO.test(text)) return false;
  return true;
}

/**
 * Municipios de más de 200.000 habitantes (INE). En ellos «lo nuevo en Madrid» son
 * demasiados avisos, así que el formulario no nombra la ciudad: habla del barrio.
 */
const CIUDADES_GRANDES = new Set([
  "madrid", "barcelona", "valencia", "sevilla", "zaragoza", "malaga", "murcia",
  "palma", "palma de mallorca", "las palmas de gran canaria", "bilbao", "alicante",
  "alacant", "cordoba", "valladolid", "vigo", "gijon", "l'hospitalet de llobregat",
  "hospitalet de llobregat", "vitoria", "vitoria-gasteiz", "a coruna", "la coruna",
  "elche", "elx", "granada", "terrassa", "badalona", "oviedo", "cartagena", "sabadell",
  "jerez de la frontera", "mostoles", "santa cruz de tenerife", "pamplona", "iruna",
  "almeria", "alcala de henares", "fuenlabrada",
]);

export function isCiudadGrande(municipio: string | null | undefined): boolean {
  const name = fold(municipio).replace(/^(.+), (la|el|a|l')$/, "$2 $1").replace(/\s*\/.*$/, "");
  return CIUDADES_GRANDES.has(name);
}

export function resolveSeguirOferta(input: {
  fase?: string | null;
  faseNormalizada?: string | null;
  estado?: string | null;
  instrumentos?: Array<string | null | undefined>;
  barrio?: string | null;
  distrito?: string | null;
  ambito?: string | null;
  municipio?: string | null;
}): { aviso: SeguirAviso; lugar: string | null } {
  const planGeneral = isPlanGeneral(input.instrumentos ?? []);
  const cerrado = isExpedienteCerrado(input);
  const municipio = cleanPlaceLabel(input.municipio);
  const barrio = cleanPlaceLabel(input.barrio) ?? cleanPlaceLabel(input.distrito) ?? cleanPlaceLabel(input.ambito);
  // En una ciudad grande no se nombra la ciudad: sin barrio conocido, el texto dice «tu barrio».
  const ciudad = isCiudadGrande(input.municipio) ? null : municipio;
  const local = barrio ?? ciudad;
  if (planGeneral) return { aviso: "zona", lugar: isCiudadGrande(input.municipio) ? null : municipio ?? local };
  if (cerrado) return { aviso: "zona", lugar: local };
  return { aviso: "proyecto", lugar: local };
}

function lugarEn(lugar: string | null): string {
  return lugar ? `en ${lugar}` : "en tu barrio";
}

export function seguirCopy(aviso: SeguirAviso, lugar: string | null): SeguirCopy {
  if (aviso === "zona") {
    const donde = lugarEn(lugar);
    const titulo = lugar ? `Avísame de lo nuevo en ${lugar}` : "Avísame de lo nuevo en tu barrio";
    return {
      aviso,
      lugar,
      titulo,
      texto: `Te avisamos por correo cuando haya un proyecto nuevo o cambie el planeamiento ${donde}.`,
      boton: "Avísame",
      botonDocumentos: titulo,
      barra: titulo,
      legal: `Solo usaremos tu correo para avisarte de novedades urbanísticas ${donde}.`,
      confirmacion: `Te avisaremos por correo cuando haya novedades urbanísticas ${donde}.`,
      pregunta: "¿Por qué quieres estos avisos?",
      ya: lugar ? `Ya te avisaremos de lo nuevo en ${lugar}.` : "Ya te avisaremos de lo nuevo en tu barrio.",
    };
  }
  return {
    aviso,
    lugar,
    titulo: "Sigue este proyecto",
    texto: "Te avisamos por correo cuando cambie de fase o se publique documentación nueva.",
    boton: "Seguir proyecto",
    botonDocumentos: "Avísame cuando se publique un documento nuevo",
    barra: "Seguir este proyecto",
    legal: "Solo usaremos tu correo para avisarte de los cambios de fase y de la documentación nueva de este proyecto.",
    confirmacion: "Te avisaremos por correo cuando cambie de fase o se publique documentación nueva.",
    pregunta: "¿Por qué sigues este proyecto?",
    ya: "Ya sigues este proyecto.",
  };
}

export type FollowSignup = {
  intent: "alta";
  email: string;
  source: SeguirSource;
  contextKey: string;
  posicion: SeguirPosicion | null;
  municipio: string | null;
  referrer: string | null;
  utm: Record<string, string> | null;
  aviso: SeguirAviso | null;
  ambito: string | null;
};

export type FollowSegment = {
  intent: "segmento";
  email: string;
  contextKey: string;
  segmento: SeguirSegmento;
};

export function cleanFollowSignup(body: unknown): FollowSignup | null {
  if (!body || typeof body !== "object") return null;
  const raw = body as Record<string, unknown>;
  if (raw.intent != null && raw.intent !== "alta") return null;
  if (typeof raw.source !== "string" || !(SEGUIR_SOURCES as readonly string[]).includes(raw.source)) return null;
  const source = raw.source as SeguirSource;
  const email = normalizeEmail(raw.email);
  if (!email) return null;

  if (source !== "project") {
    if (raw.posicion != null || raw.municipio != null || raw.referrer != null || raw.utm != null || raw.aviso != null || raw.ambito != null) return null;
    return { intent: "alta", email, source, contextKey: "", posicion: null, municipio: null, referrer: null, utm: null, aviso: null, ambito: null };
  }

  if (typeof raw.contextKey !== "string") return null;
  const contextKey = raw.contextKey.trim();
  if (!contextKey || contextKey.length > 200) return null;
  const posicion = cleanPosicion(raw.posicion);
  if (!posicion) return null;

  const municipio = raw.municipio == null || raw.municipio === "" ? null : cleanPlace(raw.municipio);
  if ((raw.municipio != null && raw.municipio !== "") && !municipio) return null;
  const referrer = raw.referrer == null || raw.referrer === "" ? null : cleanReferrer(raw.referrer);
  if ((raw.referrer != null && raw.referrer !== "") && !referrer) return null;
  const utmResult = cleanUtm(raw.utm);
  if (!utmResult.ok) return null;
  const aviso = raw.aviso === "proyecto" || raw.aviso === "zona" ? raw.aviso : null;
  if (!aviso) return null;
  const ambito = raw.ambito == null || raw.ambito === "" ? null : cleanPlaceLabel(typeof raw.ambito === "string" ? raw.ambito : null);
  if (raw.ambito != null && raw.ambito !== "" && !ambito) return null;

  return { intent: "alta", email, source, contextKey, posicion, municipio, referrer, utm: utmResult.utm, aviso, ambito };
}

export function cleanFollowSegment(body: unknown): FollowSegment | null {
  if (!body || typeof body !== "object") return null;
  const raw = body as Record<string, unknown>;
  if (raw.intent !== "segmento" || raw.source !== "project") return null;
  const email = normalizeEmail(raw.email);
  const segmento = cleanSegmento(raw.segmento);
  if (!email || !segmento || typeof raw.contextKey !== "string") return null;
  const contextKey = raw.contextKey.trim();
  if (!contextKey || contextKey.length > 200) return null;
  return { intent: "segmento", email, contextKey, segmento };
}

/** Referrer without query string, and only when it comes from another site. UTM from the current page. */
export function readAttribution(pageUrl: string, referrer: string): { referrer: string | null; utm: Record<string, string> | null } {
  let pageHost = "";
  let utm: Record<string, string> | null = null;
  try {
    const url = new URL(pageUrl);
    pageHost = url.hostname.replace(/^www\./, "");
    const found: Record<string, string> = {};
    for (const key of UTM_KEYS) {
      const value = url.searchParams.get(key)?.trim() ?? "";
      if (!value || value.length > 120 || CONTROL.test(value) || value.includes("@")) continue;
      found[key] = value;
    }
    if (Object.keys(found).length) utm = found;
  } catch {
    /* Ignore a malformed page URL. */
  }

  let clean: string | null = null;
  try {
    const ref = new URL(referrer);
    const host = ref.hostname.replace(/^www\./, "");
    if (host && host !== pageHost && (ref.protocol === "http:" || ref.protocol === "https:")) {
      const value = `${ref.origin}${ref.pathname}`.replace(/\/$/, "") || ref.origin;
      clean = cleanReferrer(value.slice(0, 300));
    }
  } catch {
    /* Direct visits have no referrer. */
  }
  return { referrer: clean, utm };
}

export function claimOnce(seen: { has(key: string): boolean; add(key: string): void }, key: string): boolean {
  if (seen.has(key)) return false;
  seen.add(key);
  return true;
}

const STORAGE_KEY = "homes_seguir_proyecto_v1";
const BAR_KEY = "homes_seguir_barra_v1";

export type StoredFollow = { segmento: SeguirSegmento | null };

export function readStoredFollow(projectId: string): StoredFollow | null {
  if (typeof window === "undefined") return null;
  try {
    const all = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    const row = all && typeof all === "object" ? (all as Record<string, unknown>)[projectId] : null;
    if (!row || typeof row !== "object") return null;
    const segmento = cleanSegmento((row as { segmento?: unknown }).segmento);
    return { segmento };
  } catch {
    return null;
  }
}

export function writeStoredFollow(projectId: string, value: StoredFollow) {
  if (typeof window === "undefined") return;
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    const all = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, StoredFollow> : {};
    all[projectId] = { segmento: value.segmento };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    /* Private mode keeps the signup for this page view only. */
  }
}

export function barDismissed(projectId: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    const ids = JSON.parse(sessionStorage.getItem(BAR_KEY) || "[]");
    return Array.isArray(ids) && ids.includes(projectId);
  } catch {
    return false;
  }
}

export function dismissBar(projectId: string) {
  if (typeof window === "undefined") return;
  try {
    const parsed = JSON.parse(sessionStorage.getItem(BAR_KEY) || "[]");
    const ids = Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string") : [];
    if (!ids.includes(projectId)) ids.push(projectId);
    sessionStorage.setItem(BAR_KEY, JSON.stringify(ids.slice(-30)));
  } catch {
    /* Closing still hides the bar until the next full load. */
  }
}
