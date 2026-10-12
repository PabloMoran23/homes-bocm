export const EVENT_NAMES = ["page_view", "page_engagement", "document_click", "outbound_click", "boletin_buscar", "ficha_proyecto_ver", "estadisticas_filtro", "mapa_buscar", "mapa_seleccionar", "ficha_pestana"] as const;
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
const NUMBERS: Record<string, number> = { active_seconds: 86400, scroll_percent: 100, radius_m: 3000, months: 120, resultados: 100000, activos: 20, caracteres: 200 };
const STRINGS = new Set(["id", "kind", "modo", "tab", "distrito", "barrio", "municipio", "destination_host", "document_type", "distritos", "actuaciones", "procedimientos", "usos", "anio", "categoriaProyecto", "tipoObra", "tipoLegal", "escala", "iniciativa"]);
type CleanEvent = { id: string; session: string; page: string; name: string; path: string; source: string; at: number; props: Record<string, string | number | boolean> };

export function sanitizeAnalyticsBatch(body: unknown, now = Date.now()): CleanEvent[] | null {
  if (!body || typeof body !== "object") return null;
  const input = body as { events?: unknown };
  if (!Array.isArray(input.events) || input.events.length < 1 || input.events.length > 20) return null;
  const output: CleanEvent[] = [];
  for (const raw of input.events) {
    if (!raw || typeof raw !== "object") return null;
    const event = raw as Record<string, unknown>;
    if (![event.id, event.session, event.page].every(v => typeof v === "string" && UUID.test(v))) return null;
    if (!EVENT_NAMES.includes(event.name as typeof EVENT_NAMES[number])) return null;
    if (typeof event.path !== "string" || !/^\/[a-zA-Z0-9/%:_-]*$/.test(event.path) || event.path.length > 240 || event.path.startsWith("/api") || event.path.startsWith("/ubicacion/")) return null;
    if (!["google", "bing", "direct", "internal", "other"].includes(String(event.source))) return null;
    if (typeof event.at !== "number" || !Number.isFinite(event.at) || event.at < now - 86400000 || event.at > now + 60000) return null;
    const props: CleanEvent["props"] = {};
    if (event.props && typeof event.props === "object" && !Array.isArray(event.props)) {
      for (const [key, value] of Object.entries(event.props)) {
        if (key in NUMBERS && typeof value === "number" && Number.isFinite(value)) props[key] = Math.max(0, Math.min(NUMBERS[key], Math.round(value)));
        else if (STRINGS.has(key) && typeof value === "string" && value.length <= 160 && !/[?@\n\r]/.test(value)) props[key] = value;
      }
    }
    output.push({ id: event.id as string, session: event.session as string, page: event.page as string, name: event.name as string, path: event.path, source: event.source as string, at: event.at, props });
  }
  return output;
}
