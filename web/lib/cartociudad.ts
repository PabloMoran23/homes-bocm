import { isSpainLocation, type AddressLocation } from "./address-search";

export type AddressSuggestion = {
  id: string;
  type: "portal" | "callejero";
  label: string;
  municipality: string;
  postalCode: string;
};

type Candidate = {
  id?: string;
  type?: string;
  address?: string;
  muni?: string;
  muniCode?: string;
  postalCode?: string;
  lat?: number;
  lng?: number;
};

const BASE = "https://www.cartociudad.es/geocoder/api/geocoder/";
const normalize = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const roadType = /^(calle|c|avenida|av|avda|paseo|passeig|carrer|cami|camino|plaza|placa|rambla|ronda|carretera|travesia|rua|kalea|etorbidea|via|urbanizacion)\b/;
const stopWords = new Set(["calle", "c", "de", "del", "la", "las", "los", "el", "avenida", "paseo", "carrer", "passeig"]);

async function request(method: string, params: URLSearchParams): Promise<unknown> {
  const response = await fetch(`${BASE}${method}?${params}`, {
    signal: AbortSignal.timeout(7000),
    next: { revalidate: 86400 },
  });
  if (!response.ok) throw new Error("No se pudo consultar el callejero");
  return response.json();
}

export async function suggestAddresses(query: string): Promise<AddressSuggestion[]> {
  // CartoCiudad sometimes interprets an unprefixed street name as a road type.
  // Try the explicit street form as well; never invent a house number or city.
  const queries = roadType.test(normalize(query)) ? [query] : [query, `calle ${query}`];
  const responses = await Promise.allSettled(queries.map(q => request("candidates", new URLSearchParams({
    q, limit: "8",
    no_process: "municipio,provincia,comunidad autonoma,poblacion,toponimo,carretera,ngbe,refcatastral,expendeduria,punto_recarga_electrica",
  }))));
  const lists = responses.flatMap(result => result.status === "fulfilled" && Array.isArray(result.value) ? [result.value as Candidate[]] : []);
  if (!lists.length) throw new Error("El callejero no está disponible");
  const seen = new Set<string>();
  const candidates = lists.flat().flatMap((item): AddressSuggestion[] => {
    if (!item || !item.id || !item.address || !item.muni || !/^\d{5}$/.test(String(item.muniCode))
      || (item.type !== "portal" && item.type !== "callejero")) return [];
    const key = `${item.type}:${item.id}`;
    if (seen.has(key)) return [];
    seen.add(key);
    return [{ id: item.id, type: item.type, label: item.address, municipality: item.muni, postalCode: item.postalCode || "" }];
  });
  const words = normalize(query).split(" ").filter(word => !stopWords.has(word));
  const score = (item: AddressSuggestion) => {
    const tokens = normalize(item.label).split(" ");
    // Keep the requested number and municipality ahead of fuzzy near matches.
    return words.reduce((sum, word) => sum + (tokens.includes(word) ? (/^\d+$/.test(word) ? 5 : 2)
      : word.length >= 3 && !/^\d+$/.test(word) && tokens.some(token => token.startsWith(word)) ? 1 : 0), 0);
  };
  return candidates.sort((a, b) => score(b) - score(a) || (score(a) > 0 ? a.label.length - b.label.length : 0)).slice(0, 6);
}

export async function resolveAddress(id: string, type: AddressSuggestion["type"]): Promise<AddressLocation> {
  const item = await request("find", new URLSearchParams({ id, type })) as Candidate | null;
  const location = { lat: Number(item?.lat), lng: Number(item?.lng) };
  if (!item?.address || !item.muni || !/^\d{5}$/.test(String(item.muniCode)) || !isSpainLocation(location)) {
    throw new Error("No se pudo localizar esa dirección");
  }
  return { ...location, label: item.address.includes(",") ? item.address : `${item.address}, ${item.muni}`, municipality: item.muni };
}
